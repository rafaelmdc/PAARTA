(() => {
  const PENDING_UPLOAD_KEY = "homorepeat:pending_upload_id";

  function getCookie(name) {
    const cookies = document.cookie ? document.cookie.split(";") : [];
    const prefix = `${name}=`;
    for (const cookie of cookies) {
      const trimmed = cookie.trim();
      if (trimmed.startsWith(prefix)) {
        return decodeURIComponent(trimmed.slice(prefix.length));
      }
    }
    return "";
  }

  function csrfToken() {
    const meta = document.querySelector("meta[name='csrf-token']");
    if (meta && meta.content) {
      return meta.content;
    }
    return getCookie("csrftoken");
  }

  function uploadUrl(template, uploadId) {
    return template.replace("__upload_id__", uploadId).replace("{upload_id}", uploadId);
  }

  async function parseJsonResponse(response) {
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.error || `Upload request failed with ${response.status}`);
    }
    return payload;
  }

  async function postJson(url, payload) {
    const response = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken(),
      },
      body: JSON.stringify(payload),
    });
    return parseJsonResponse(response);
  }

  async function getJson(url) {
    const response = await fetch(url, {
      method: "GET",
      credentials: "same-origin",
      headers: { "Accept": "application/json" },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.error || `Request failed with ${response.status}`);
    }
    return payload;
  }

  async function sha256Hex(blob) {
    const buffer = await blob.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest("SHA-256", buffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
  }

  async function postChunk(url, chunkIndex, chunkBlob) {
    const chunkSha256 = await sha256Hex(chunkBlob);
    const formData = new FormData();
    formData.append("chunk_index", String(chunkIndex));
    formData.append("chunk_sha256", chunkSha256);
    formData.append("chunk", chunkBlob, `${chunkIndex}.part`);

    const response = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Accept": "application/json",
        "X-CSRFToken": csrfToken(),
      },
      body: formData,
    });
    return parseJsonResponse(response);
  }

  async function retry(operation, retryCount) {
    let lastError = null;
    for (let attempt = 0; attempt <= retryCount; attempt += 1) {
      try {
        return await operation();
      } catch (error) {
        lastError = error;
      }
    }
    throw lastError;
  }

  /**
   * Try to load resumable state from the status endpoint.
   * Returns a map of chunk index -> {sha256} for chunks the server has already
   * accepted, or an empty map if the stored upload doesn't match this file.
   */
  async function loadResumeState(file, statusUrlTemplate) {
    const storedUploadId = sessionStorage.getItem(PENDING_UPLOAD_KEY);
    if (!storedUploadId || !statusUrlTemplate) {
      return { uploadId: null, serverChunks: {} };
    }

    try {
      const status = await getJson(uploadUrl(statusUrlTemplate, storedUploadId));
      const resumable =
        status.status === "receiving" &&
        status.size_bytes === file.size &&
        status.filename === file.name;

      if (!resumable) {
        return { uploadId: null, serverChunks: {} };
      }

      const serverChunks = {};
      for (const chunk of (status.received_chunks || [])) {
        serverChunks[chunk.index] = chunk;
      }
      return { uploadId: storedUploadId, serverChunks };
    } catch (_err) {
      return { uploadId: null, serverChunks: {} };
    }
  }

  async function uploadFile(options) {
    const file = options.file;
    const retryCount = options.retryCount ?? 2;
    const onProgress = options.onProgress || (() => {});

    // Attempt to resume a previous interrupted upload
    const { uploadId: resumedUploadId, serverChunks } = await loadResumeState(
      file,
      options.statusUrlTemplate,
    );

    let uploadId = resumedUploadId;
    let chunkSizeBytes = options.chunkSizeBytes;

    if (!uploadId) {
      const startPayload = await postJson(options.startUrl, {
        filename: file.name,
        size_bytes: file.size,
        total_chunks: Math.ceil(file.size / options.chunkSizeBytes),
      });
      uploadId = startPayload.upload_id;
      chunkSizeBytes = startPayload.chunk_size_bytes || options.chunkSizeBytes;
      sessionStorage.setItem(PENDING_UPLOAD_KEY, uploadId);
    }

    const totalChunks = Math.ceil(file.size / chunkSizeBytes);

    for (let chunkIndex = 0; chunkIndex < totalChunks; chunkIndex += 1) {
      const start = chunkIndex * chunkSizeBytes;
      const end = Math.min(start + chunkSizeBytes, file.size);
      const chunkBlob = file.slice(start, end);
      const chunkUrl = uploadUrl(options.chunkUrlTemplate, uploadId);
      const serverChunk = serverChunks[chunkIndex];

      if (serverChunk && serverChunk.sha256) {
        const localSha256 = await sha256Hex(chunkBlob);
        if (localSha256 === serverChunk.sha256) {
          onProgress({
            uploadId,
            chunkIndex,
            totalChunks,
            uploadedChunks: chunkIndex + 1,
            percent: Math.round(((chunkIndex + 1) / totalChunks) * 1000) / 10,
            skipped: true,
          });
          continue;
        }
        // Different content at the same index — unresolvable conflict
        sessionStorage.removeItem(PENDING_UPLOAD_KEY);
        throw new Error(
          `Chunk ${chunkIndex} does not match server state. ` +
          "The selected file may have changed since the upload began.",
        );
      }

      await retry(() => postChunk(chunkUrl, chunkIndex, chunkBlob), retryCount);
      onProgress({
        uploadId,
        chunkIndex,
        totalChunks,
        uploadedChunks: chunkIndex + 1,
        percent: Math.round(((chunkIndex + 1) / totalChunks) * 1000) / 10,
        skipped: false,
      });
    }

    sessionStorage.removeItem(PENDING_UPLOAD_KEY);
    return postJson(uploadUrl(options.completeUrlTemplate, uploadId), {});
  }

  function bindUploadForms() {
    const forms = Array.from(document.querySelectorAll("[data-import-upload-form]"));
    forms.forEach((form) => {
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const fileInput = form.querySelector("[data-import-upload-file]");
        const progress = form.querySelector("[data-import-upload-progress]");
        const status = form.querySelector("[data-import-upload-status]");
        const file = fileInput && fileInput.files ? fileInput.files[0] : null;
        if (!file) {
          if (status) {
            status.textContent = "Choose a zip file first.";
          }
          return;
        }

        try {
          if (status) {
            status.textContent = "Uploading";
          }
          await uploadFile({
            file,
            startUrl: form.dataset.uploadStartUrl,
            chunkUrlTemplate: form.dataset.uploadChunkUrlTemplate,
            completeUrlTemplate: form.dataset.uploadCompleteUrlTemplate,
            statusUrlTemplate: form.dataset.uploadStatusUrlTemplate,
            chunkSizeBytes: Number.parseInt(form.dataset.uploadChunkSizeBytes || "8388608", 10),
            onProgress: ({ percent }) => {
              if (progress) {
                progress.value = percent;
              }
            },
          });
          if (status) {
            status.textContent = "Received";
          }
        } catch (error) {
          if (status) {
            status.textContent = error.message;
          }
        }
      });
    });
  }

  window.HomoRepeatImportUploads = {
    uploadFile,
    csrfToken,
  };

  document.addEventListener("DOMContentLoaded", bindUploadForms);
})();
