(() => {
  const chartShell = window.HomorepeatStatsChartShell;
  if (!chartShell) return;

  const parsePayload = chartShell.parsePayload;
  const chartHeightForRowCount = chartShell.chartHeightForRowCount;
  const defaultZoomState = chartShell.defaultZoomState;
  const normalizeZoomState = chartShell.normalizeZoomState;
  const buildXAxisZoom = chartShell.buildXAxisZoom;
  const buildYAxisZoom = chartShell.buildYAxisZoom;
  const installWheelHandler = chartShell.installWheelHandler;
  const resolveZoomState = chartShell.resolveZoomState;

  const PAYLOAD_IDS = {
    preference: "codon-composition-length-preference-overview-payload",
    dominance: "codon-composition-length-dominance-overview-payload",
    shift: "codon-composition-length-shift-overview-payload",
    browse: "codon-composition-length-browse-payload",
  };
  const CODON_COLORS = [
    "#0f5964",
    "#d06e37",
    "#7b5ea7",
    "#2f8f5b",
    "#b04f6f",
    "#9a7b2f",
  ];
  const DEFAULT_VISIBLE_COLUMNS = 16;
  const DEFAULT_BROWSE_WINDOW_SIZE = 12;

  function supportOpacity(cell, payload) {
    const maxObservationCount = Math.max(1, payload.maxObservationCount || 1);
    const observationCount = Math.max(0, cell.observationCount || 0);
    return Math.max(0.62, Math.min(1, 0.62 + 0.38 * Math.sqrt(observationCount / maxObservationCount)));
  }

  function modePayload(payloads, mode) {
    return payloads[mode] || null;
  }

  function activePayload(payloads, requestedMode) {
    const requested = modePayload(payloads, requestedMode);
    if (requested && requested.available) return requested;
    return payloads.preference.available
      ? payloads.preference
      : (payloads.dominance.available ? payloads.dominance : payloads.shift);
  }

  function xLabels(payload) {
    if (payload.mode === "shift") {
      return (payload.transitions || []).map((transition) => transition.label);
    }
    return (payload.visibleBins || []).map((bin) => bin.label);
  }

  function yLabels(payload) {
    return (payload.taxa || []).map((taxon) => taxon.taxonName);
  }

  function cellXIndex(cell, payload) {
    return payload.mode === "shift" ? cell.transitionIndex : cell.binIndex;
  }

  function defaultColumnZoomState(columnCount) {
    if (columnCount <= DEFAULT_VISIBLE_COLUMNS) return null;
    return {
      startValue: 0,
      endValue: DEFAULT_VISIBLE_COLUMNS - 1,
    };
  }

  function normalizeColumnZoomState(columnCount, zoomState) {
    if (columnCount <= DEFAULT_VISIBLE_COLUMNS) return null;
    const fallback = defaultColumnZoomState(columnCount);
    const startValue = Math.max(0, Math.min(columnCount - 1, Math.round(
      typeof zoomState?.startValue === "number" ? zoomState.startValue : fallback.startValue,
    )));
    const endValue = Math.max(startValue, Math.min(columnCount - 1, Math.round(
      typeof zoomState?.endValue === "number" ? zoomState.endValue : fallback.endValue,
    )));
    return { startValue, endValue };
  }

  function columnZoomStateFromParams(params, columnCount) {
    if (!params) return null;
    const events = Array.isArray(params.batch) && params.batch.length > 0 ? params.batch : [params];
    const payload = events.find((entry) => entry && entry.dataZoomId === "codon-length-x-slider");
    if (!payload || payload.dataZoomId !== "codon-length-x-slider") return null;
    if (payload.startValue != null || payload.endValue != null) {
      return normalizeColumnZoomState(columnCount, {
        startValue: payload.startValue,
        endValue: payload.endValue,
      });
    }
    return null;
  }

  function labelInterval(columnCount) {
    if (columnCount <= 32) return 0;
    if (columnCount <= 96) return 4;
    if (columnCount <= 180) return 9;
    return 19;
  }

  function seriesData(payload) {
    return (payload.cells || []).map((cell) => {
      const item = {
        value: [cellXIndex(cell, payload), cell.rowIndex, cell.value],
        cell,
        itemStyle: {
          opacity: supportOpacity(
            payload.mode === "shift" ? cell.nextSupport : cell,
            payload,
          ),
        },
      };
      if (payload.mode === "dominance") {
        item.itemStyle.color = CODON_COLORS[Math.max(0, cell.dominantCodonIndex) % CODON_COLORS.length];
        item.itemStyle.opacity = Math.max(item.itemStyle.opacity * Math.max(0.35, cell.dominanceMargin || 0), 0.28);
      }
      return item;
    });
  }

  function formatShares(rows) {
    return (rows || [])
      .map((row) => `${row.codon}: ${(row.share * 100).toFixed(1)}%`)
      .join("<br>");
  }

  function formatShare(value) {
    return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "-";
  }

  function tooltipHtml(payload, cell) {
    const taxon = payload.taxa[cell.rowIndex] || {};
    if (payload.mode === "shift") {
      return [
        `<strong>${taxon.taxonName || "Taxon"}</strong>`,
        `${cell.previousBin.label} -> ${cell.nextBin.label}`,
        `${payload.metricLabel}: ${cell.shift.toFixed(3)}`,
        `Previous support: ${cell.previousSupport.observationCount} observations, ${cell.previousSupport.speciesCount} species`,
        `Next support: ${cell.nextSupport.observationCount} observations, ${cell.nextSupport.speciesCount} species`,
        "<hr>",
        `<strong>${cell.previousBin.label}</strong><br>${formatShares(cell.previousCodonShares)}`,
        `<strong>${cell.nextBin.label}</strong><br>${formatShares(cell.nextCodonShares)}`,
      ].join("<br>");
    }
    if (payload.mode === "preference") {
      return [
        `<strong>${taxon.taxonName || "Taxon"}</strong>`,
        cell.binLabel,
        `${payload.metricLabel}: ${cell.preference.toFixed(3)}`,
        `${cell.codonA}: ${(cell.codonAShare * 100).toFixed(1)}%`,
        `${cell.codonB}: ${(cell.codonBShare * 100).toFixed(1)}%`,
        `Support: ${cell.observationCount} observations, ${cell.speciesCount} species`,
      ].join("<br>");
    }
    return [
      `<strong>${taxon.taxonName || "Taxon"}</strong>`,
      cell.binLabel,
      `Dominant codon: ${cell.dominantCodon}`,
      `Dominance margin: ${cell.dominanceMargin.toFixed(3)}`,
      `Support: ${cell.observationCount} observations, ${cell.speciesCount} species`,
      "<hr>",
      formatShares(cell.codonShares),
    ].join("<br>");
  }

  function visualMap(payload) {
    if (payload.mode === "dominance") return [];
    return [
      {
        min: payload.valueMin,
        max: payload.valueMax,
        dimension: 2,
        calculable: true,
        orient: "vertical",
        right: 16,
        top: 42,
        bottom: 72,
        inRange: {
          color: payload.mode === "preference"
            ? ["#0f5964", "#f2efe6", "#d06e37"]
            : ["#f2efe6", "#d06e37"],
        },
        textStyle: { color: "#63727a" },
      },
    ];
  }

  function chartOption(payload, rowZoomState, columnZoomState) {
    const labels = xLabels(payload);
    const xZoom = buildXAxisZoom(labels.length, columnZoomState, {
      insideId: "codon-length-x-inside",
      sliderId: "codon-length-x-slider",
      left: 0,
      right: payload.mode === "dominance" ? 28 : 96,
      bottom: 24,
      height: 18,
    });
    return {
      animation: false,
      grid: {
        left: 172,
        right: payload.mode === "dominance" ? 28 : 96,
        top: 36,
        bottom: columnZoomState ? 112 : 76,
        containLabel: false,
      },
      tooltip: {
        confine: true,
        formatter: (params) => tooltipHtml(payload, params.data.cell),
      },
      xAxis: {
        type: "category",
        data: labels,
        axisLabel: {
          color: "#63727a",
          rotate: 0,
          interval: labelInterval(labels.length),
          hideOverlap: true,
          width: 52,
          overflow: "truncate",
        },
        axisTick: { alignWithLabel: true },
      },
      yAxis: {
        type: "category",
        inverse: true,
        data: yLabels(payload),
        axisLabel: {
          color: "#17242c",
          width: 156,
          overflow: "truncate",
        },
      },
      dataZoom: [
        ...buildYAxisZoom(payload.visibleTaxaCount || 0, rowZoomState, {
        right: payload.mode === "dominance" ? 8 : 72,
        top: 36,
          bottom: columnZoomState ? 112 : 76,
        }),
        ...xZoom,
      ],
      visualMap: visualMap(payload),
      series: [
        {
          type: "heatmap",
          data: seriesData(payload),
          emphasis: {
            itemStyle: {
              borderColor: "#17242c",
              borderWidth: 1,
            },
          },
        },
      ],
    };
  }

  function syncButtons(buttons, activeMode, payloads) {
    buttons.forEach((button) => {
      const mode = button.dataset.overviewMode;
      const payload = modePayload(payloads, mode);
      const isActive = mode === activeMode;
      button.disabled = !payload || !payload.available;
      button.classList.toggle("btn-brand", isActive);
      button.classList.toggle("btn-outline-secondary", !isActive);
      button.setAttribute("aria-pressed", isActive ? "true" : "false");
    });
  }

  function syncDescriptions(descriptions, activeMode) {
    descriptions.forEach((description) => {
      description.hidden = description.dataset.overviewMode !== activeMode;
    });
  }

  function mountOverview() {
    const container = document.getElementById("codon-composition-length-overview-chart");
    if (!container || typeof window.echarts === "undefined") return;

    const payloads = {
      preference: parsePayload(PAYLOAD_IDS.preference) || {},
      dominance: parsePayload(PAYLOAD_IDS.dominance) || {},
      shift: parsePayload(PAYLOAD_IDS.shift) || {},
    };
    let payload = activePayload(payloads, container.dataset.defaultOverviewMode || "preference");
    const emptyMessage = document.querySelector("[data-codon-length-overview-empty]");
    const buttons = Array.from(document.querySelectorAll("[data-codon-length-overview-mode-button]"));
    const descriptions = Array.from(document.querySelectorAll("[data-codon-length-overview-description]"));

    if (!payload || !payload.available) {
      container.hidden = true;
      syncButtons(buttons, "", payloads);
      return;
    }

    let currentMode = payload.mode;
    let currentRowZoomState = normalizeZoomState(
      payload.visibleTaxaCount || 0,
      defaultZoomState(payload.visibleTaxaCount || 0),
    );
    let currentColumnZoomState = normalizeColumnZoomState(
      xLabels(payload).length,
      defaultColumnZoomState(xLabels(payload).length),
    );
    container.style.height = `${chartHeightForRowCount(payload.visibleTaxaCount || 0, { minimumHeight: 360 })}px`;
    const chart = window.echarts.init(container);
    installWheelHandler(chart, payload.visibleTaxaCount || 0, () => currentRowZoomState);

    function render() {
      payload = modePayload(payloads, currentMode);
      currentRowZoomState = normalizeZoomState(payload.visibleTaxaCount || 0, currentRowZoomState);
      currentColumnZoomState = normalizeColumnZoomState(xLabels(payload).length, currentColumnZoomState);
      container.hidden = false;
      if (emptyMessage) emptyMessage.hidden = true;
      syncButtons(buttons, currentMode, payloads);
      syncDescriptions(descriptions, currentMode);
      container.style.height = `${chartHeightForRowCount(payload.visibleTaxaCount || 0, { minimumHeight: 360 })}px`;
      chart.setOption(chartOption(payload, currentRowZoomState, currentColumnZoomState), { notMerge: true });
      chart.resize();
    }

    chart.on("datazoom", (params) => {
      currentRowZoomState = resolveZoomState(chart, payload.visibleTaxaCount || 0, params);
      currentColumnZoomState = columnZoomStateFromParams(params, xLabels(payload).length)
        || currentColumnZoomState;
    });

    buttons.forEach((button) => {
      button.addEventListener("click", () => {
        const nextMode = button.dataset.overviewMode;
        const nextPayload = modePayload(payloads, nextMode);
        if (!nextPayload || !nextPayload.available || nextMode === currentMode) return;
        currentMode = nextMode;
        currentRowZoomState = normalizeZoomState(
          nextPayload.visibleTaxaCount || 0,
          defaultZoomState(nextPayload.visibleTaxaCount || 0),
        );
        currentColumnZoomState = normalizeColumnZoomState(
          xLabels(nextPayload).length,
          defaultColumnZoomState(xLabels(nextPayload).length),
        );
        render();
      });
    });

    window.addEventListener("resize", () => chart.resize());
    render();
  }

  function browseSeries(payload, panel) {
    const codons = payload.visibleCodons || [];
    if (codons.length === 2) {
      return codons.map((codon, codonIndex) => ({
        name: codon,
        type: "line",
        smooth: false,
        showSymbol: true,
        symbolSize: 4,
        connectNulls: false,
        areaStyle: { opacity: codonIndex === 0 ? 0.22 : 0 },
        lineStyle: { width: 2 },
        itemStyle: { color: CODON_COLORS[codonIndex % CODON_COLORS.length] },
        data: panel.bins.map((bin) => {
          const shareRow = (bin.codonShares || []).find((row) => row.codon === codon);
          return bin.occupied && shareRow ? shareRow.share : null;
        }),
      }));
    }
    return codons.map((codon, codonIndex) => ({
      name: codon,
      type: "bar",
      stack: "composition",
      barWidth: "72%",
      itemStyle: {
        color: CODON_COLORS[codonIndex % CODON_COLORS.length],
      },
      data: panel.bins.map((bin) => {
        const shareRow = (bin.codonShares || []).find((row) => row.codon === codon);
        return bin.occupied && shareRow ? shareRow.share : null;
      }),
    }));
  }

  function browseTooltip(panel, dataIndex) {
    const bin = panel.bins[dataIndex];
    if (!bin) return "";
    const lines = [
      `<strong>${panel.taxonName}</strong>`,
      bin.bin.label,
    ];
    if (!bin.occupied) {
      lines.push("No occupied observations in this bin");
      return lines.join("<br>");
    }
    lines.push(`Support: ${bin.observationCount} observations, ${bin.speciesCount} species`);
    lines.push(...(bin.codonShares || []).map((row) => `${row.codon}: ${formatShare(row.share)}`));
    return lines.join("<br>");
  }

  function browseChartOption(payload, panel) {
    const labels = (payload.visibleBins || []).map((bin) => bin.label);
    const isTwoCodon = (payload.visibleCodons || []).length === 2;
    return {
      animation: false,
      color: CODON_COLORS,
      grid: {
        left: 48,
        right: 18,
        top: isTwoCodon ? 34 : 42,
        bottom: 52,
      },
      legend: {
        show: true,
        top: 10,
        type: "scroll",
        textStyle: { color: "#63727a" },
      },
      tooltip: {
        trigger: "axis",
        confine: true,
        formatter(params) {
          const firstParam = Array.isArray(params) ? params[0] : params;
          return browseTooltip(panel, firstParam?.dataIndex ?? 0);
        },
      },
      xAxis: {
        type: "category",
        data: labels,
        axisLabel: {
          color: "#63727a",
          interval: labelInterval(labels.length),
          hideOverlap: true,
          width: 48,
          overflow: "truncate",
        },
        axisTick: { alignWithLabel: true },
      },
      yAxis: {
        type: "value",
        min: 0,
        max: 1,
        axisLabel: {
          color: "#63727a",
          formatter: (value) => `${Math.round(value * 100)}%`,
        },
        splitLine: {
          lineStyle: { color: "rgba(23, 36, 44, 0.08)" },
        },
      },
      series: browseSeries(payload, panel),
    };
  }

  function buildBrowsePanel(payload, panel) {
    const panelNode = document.createElement("article");
    panelNode.className = "codon-length-browse-panel";

    const header = document.createElement("div");
    header.className = "codon-length-browse-panel__header";

    const title = document.createElement("p");
    title.className = "codon-length-browse-panel__title";
    title.textContent = panel.taxonName;

    const meta = document.createElement("p");
    meta.className = "codon-length-browse-panel__meta";
    meta.textContent = `${panel.observationCount} observations`;

    const chartNode = document.createElement("div");
    chartNode.className = "codon-length-browse-chart";

    header.append(title, meta);
    panelNode.append(header, chartNode);

    return { panelNode, chartNode, panel };
  }

  function mountBrowse() {
    const container = document.getElementById("codon-composition-length-browse");
    if (!container || typeof window.echarts === "undefined") return;

    const payload = parsePayload(PAYLOAD_IDS.browse) || {};
    const emptyMessage = document.querySelector("[data-codon-length-browse-empty]");
    const toolbar = document.querySelector("[data-codon-length-browse-toolbar]");
    const rangeNode = document.querySelector("[data-codon-length-browse-range]");
    const previousButton = document.querySelector("[data-codon-length-browse-prev]");
    const nextButton = document.querySelector("[data-codon-length-browse-next]");
    if (!payload.available || !Array.isArray(payload.panels) || payload.panels.length === 0) {
      container.hidden = true;
      if (toolbar) toolbar.hidden = true;
      return;
    }

    container.hidden = false;
    if (emptyMessage) emptyMessage.hidden = true;
    const windowSize = Math.max(1, payload.windowSize || DEFAULT_BROWSE_WINDOW_SIZE);
    let windowStart = 0;
    let charts = [];

    function disposeCharts() {
      charts.forEach((chart) => chart.dispose());
      charts = [];
    }

    function syncToolbar(windowEnd) {
      if (toolbar) toolbar.hidden = payload.panels.length <= windowSize;
      if (rangeNode) {
        rangeNode.textContent = `Showing ${windowStart + 1}-${windowEnd} of ${payload.panels.length} taxa`;
      }
      if (previousButton) previousButton.disabled = windowStart === 0;
      if (nextButton) nextButton.disabled = windowEnd >= payload.panels.length;
    }

    function renderWindow() {
      disposeCharts();
      container.replaceChildren();
      const windowEnd = Math.min(payload.panels.length, windowStart + windowSize);
      const panelEntries = payload.panels
        .slice(windowStart, windowEnd)
        .map((panel) => buildBrowsePanel(payload, panel));
      container.append(...panelEntries.map((entry) => entry.panelNode));
      charts = panelEntries.map((entry) => {
        const chart = window.echarts.init(entry.chartNode);
        chart.setOption(browseChartOption(payload, entry.panel), { notMerge: true });
        return chart;
      });
      syncToolbar(windowEnd);
      window.requestAnimationFrame(() => {
        charts.forEach((chart) => chart.resize());
      });
    }

    if (previousButton) {
      previousButton.addEventListener("click", () => {
        windowStart = Math.max(0, windowStart - windowSize);
        renderWindow();
      });
    }
    if (nextButton) {
      nextButton.addEventListener("click", () => {
        windowStart = Math.min(
          Math.max(0, payload.panels.length - windowSize),
          windowStart + windowSize,
        );
        renderWindow();
      });
    }
    window.addEventListener("resize", () => {
      charts.forEach((chart) => chart.resize());
    });
    renderWindow();
  }

  document.addEventListener("DOMContentLoaded", () => {
    mountOverview();
    mountBrowse();
  });
})();
