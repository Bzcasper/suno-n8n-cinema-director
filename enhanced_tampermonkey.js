// ==UserScript==
// @name         Suno-to-Modal Cinema Director (v3.1)
// @namespace    http://tampermonkey.net/
// @version      9.0
// @description  Production-ready: Enhanced logging, batch processing, health checks, and comprehensive error recovery
// @author       Robert Casper
// @match        https://suno.com/*
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_registerMenuCommand
// @grant        GM_notification
// @grant        unsafeWindow
// @run-at       document-start
// ==/UserScript==

(function () {
    "use strict";

    // ============================================================
    // PRODUCTION CONFIGURATION
    // ============================================================
    const CONFIG = {
        WEBHOOK_URL: "https://trap--suno-video-factory-v3-1-n8n-webhook.modal.run",
        MAX_RETRIES: 3,
        RETRY_DELAY_BASE: 1000,
        TIMEOUT: 3600000, // 1 hour for video generation
        BATCH_DELAY: 2000, // Delay between batch sends
        HEALTH_CHECK_INTERVAL: 300000, // 5 minutes
        MAX_QUEUE_SIZE: 50
    };

    const STORAGE_KEYS = {
        SENT_IDS: "suno_sent_ids_v7",
        FAILED_QUEUE: "suno_failed_queue_v7",
        STATS: "suno_stats_v7",
        LAST_HEALTH_CHECK: "suno_last_health_v7"
    };

    // ============================================================
    // STATE MANAGEMENT
    // ============================================================
    let sentIds = GM_getValue(STORAGE_KEYS.SENT_IDS, {});
    let failedQueue = GM_getValue(STORAGE_KEYS.FAILED_QUEUE, []);
    let stats = GM_getValue(STORAGE_KEYS.STATS, {
        total_sent: 0,
        total_failed: 0,
        last_sync: null,
        uptime_start: new Date().toISOString()
    });

    // ============================================================
    // ENHANCED LOGGING SYSTEM
    // ============================================================
    const Logger = {
        prefix: "[Suno Bridge v7]",
        
        info: (msg, data = null) => {
            console.log(`${Logger.prefix} ℹ️  ${msg}`, data || "");
        },
        
        success: (msg, data = null) => {
            console.log(`${Logger.prefix} ✅ ${msg}`, data || "");
            toast(msg, "success");
        },
        
        warn: (msg, data = null) => {
            console.warn(`${Logger.prefix} ⚠️  ${msg}`, data || "");
            toast(msg, "warn");
        },
        
        error: (msg, error = null) => {
            console.error(`${Logger.prefix} ❌ ${msg}`, error || "");
            toast(msg, "error");
            stats.total_failed++;
            saveStats();
        },
        
        debug: (msg, data = null) => {
            console.debug(`${Logger.prefix} 🔍 ${msg}`, data || "");
        }
    };

    // ============================================================
    // NEON HUD TOAST SYSTEM
    // ============================================================
    function toast(msg, type = "info", duration = 3500) {
        if (!document.body) {
            document.addEventListener("DOMContentLoaded", () => toast(msg, type, duration));
            return;
        }

        const palette = {
            info:    { c: "#00eaff", i: "ℹ️" },
            success: { c: "#00ff40", i: "✓" },
            error:   { c: "#ff003c", i: "✗" },
            warn:    { c: "#ffcc00", i: "⚠" }
        };

        const style = palette[type] || palette.info;
        const el = document.createElement("div");
        el.innerHTML = `<span style="margin-right: 8px;">${style.i}</span>${msg}`;

        Object.assign(el.style, {
            position: "fixed",
            bottom: "24px",
            right: "24px",
            padding: "14px 22px",
            background: "rgba(5, 5, 5, 0.95)",
            border: `1px solid ${style.c}`,
            borderLeft: `4px solid ${style.c}`,
            color: style.c,
            fontFamily: "Fira Code, Consolas, monospace",
            fontSize: "13px",
            letterSpacing: "0.5px",
            textTransform: "uppercase",
            boxShadow: `0 0 16px ${style.c}55, inset 0 0 8px ${style.c}22`,
            opacity: "0",
            transform: "translateY(20px)",
            zIndex: 999999,
            pointerEvents: "none",
            transition: "all .3s cubic-bezier(0.4, 0, 0.2, 1)",
            backdropFilter: "blur(10px)",
            borderRadius: "4px"
        });

        document.body.appendChild(el);
        requestAnimationFrame(() => {
            el.style.opacity = "1";
            el.style.transform = "translateY(0)";
        });

        setTimeout(() => {
            el.style.opacity = "0";
            el.style.transform = "translateY(10px)";
            setTimeout(() => el.remove(), 300);
        }, duration);
    }

    // ============================================================
    // STATS MANAGEMENT
    // ============================================================
    function saveStats() {
        stats.last_sync = new Date().toISOString();
        GM_setValue(STORAGE_KEYS.STATS, stats);
    }

    function showStats() {
        const uptime = Math.floor((new Date() - new Date(stats.uptime_start)) / 1000 / 60);
        const msg = `
📊 STATISTICS
━━━━━━━━━━━━━━━━
✓ Sent: ${stats.total_sent}
✗ Failed: ${stats.total_failed}
⏱️  Uptime: ${uptime}m
📦 Queue: ${failedQueue.length}
🔄 Last Sync: ${stats.last_sync ? new Date(stats.last_sync).toLocaleTimeString() : 'Never'}
        `.trim();
        
        alert(msg);
        Logger.info("Stats displayed", stats);
    }

    // ============================================================
    // HEALTH CHECK SYSTEM
    // ============================================================
    async function performHealthCheck() {
        Logger.info("Performing health check...");
        
        try {
            const response = await fetch(CONFIG.WEBHOOK_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    health_check: true,
                    timestamp: new Date().toISOString()
                })
            });

            if (response.ok) {
                Logger.success("Health check passed");
                GM_setValue(STORAGE_KEYS.LAST_HEALTH_CHECK, new Date().toISOString());
                return true;
            } else {
                Logger.warn(`Health check failed: ${response.status}`);
                return false;
            }
        } catch (error) {
            Logger.error("Health check error", error);
            return false;
        }
    }

    // Schedule periodic health checks
    setInterval(performHealthCheck, CONFIG.HEALTH_CHECK_INTERVAL);

    // ============================================================
    // ENHANCED RETRY ENGINE
    // ============================================================
    function sendToWebhook(data, attempt = 1) {
        // Check if already sent
        if (sentIds[data.id]) {
            Logger.debug(`Skipping already sent: ${data.id}`);
            return Promise.resolve();
        }

        // Check queue size
        if (failedQueue.length >= CONFIG.MAX_QUEUE_SIZE) {
            Logger.warn("Queue full, clearing old items");
            failedQueue = failedQueue.slice(-20);
            GM_setValue(STORAGE_KEYS.FAILED_QUEUE, failedQueue);
        }

        const isRetry = attempt > 1;
        const logPrefix = isRetry ? `[Retry ${attempt}/${CONFIG.MAX_RETRIES}]` : "[New]";

        Logger.info(`${logPrefix} Uploading: ${data.title}`);

        return new Promise((resolve, reject) => {
            GM_xmlhttpRequest({
                method: "POST",
                url: CONFIG.WEBHOOK_URL,
                headers: { "Content-Type": "application/json" },
                data: JSON.stringify(data),
                timeout: CONFIG.TIMEOUT,
                responseType: 'blob', // Handle binary video response

                onload: (res) => {
                    if (res.status >= 200 && res.status < 300) {
                        // Success - handle video file download
                        const blob = res.response;
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = `${data.title.replace(/[^a-z0-9]/gi, '_')}.mp4`;
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                        URL.revokeObjectURL(url);

                        sentIds[data.id] = {
                            timestamp: new Date().toISOString(),
                            title: data.title
                        };
                        GM_setValue(STORAGE_KEYS.SENT_IDS, sentIds);

                        stats.total_sent++;
                        saveStats();

                        Logger.success(`✓ Downloaded video: ${data.title}`);

                        // Remove from failed queue if present
                        failedQueue = failedQueue.filter(item => item.id !== data.id);
                        GM_setValue(STORAGE_KEYS.FAILED_QUEUE, failedQueue);

                        resolve(res);
                    } else {
                        handleSendError(res.status, data, attempt, reject);
                    }
                },

                onerror: () => handleSendError("NETWORK", data, attempt, reject),
                ontimeout: () => handleSendError("TIMEOUT", data, attempt, reject)
            });
        });
    }

    function handleSendError(code, payload, attempt, reject) {
        if (attempt < CONFIG.MAX_RETRIES) {
            const delay = CONFIG.RETRY_DELAY_BASE * Math.pow(2, attempt);
            Logger.warn(`Error ${code} — Retry in ${delay}ms`);
            
            setTimeout(() => {
                sendToWebhook(payload, attempt + 1)
                    .then(reject)
                    .catch(reject);
            }, delay);
        } else {
            // Max retries reached - add to failed queue
            Logger.error(`Failed permanently: ${payload.title} (${code})`);
            
            if (!failedQueue.some(item => item.id === payload.id)) {
                failedQueue.push({
                    ...payload,
                    failed_at: new Date().toISOString(),
                    error_code: code
                });
                GM_setValue(STORAGE_KEYS.FAILED_QUEUE, failedQueue);
            }
            
            // Show desktop notification for permanent failure
            if (GM_notification) {
                GM_notification({
                    title: "Suno Bridge - Upload Failed",
                    text: `${payload.title} failed after ${CONFIG.MAX_RETRIES} attempts`,
                    timeout: 5000
                });
            }
            
            reject(new Error(`Failed after ${CONFIG.MAX_RETRIES} attempts: ${code}`));
        }
    }

    // ============================================================
    // BATCH PROCESSING FOR FAILED QUEUE
    // ============================================================
    async function retryFailedQueue() {
        if (failedQueue.length === 0) {
            toast("No failed items to retry", "info");
            return;
        }

        Logger.info(`Retrying ${failedQueue.length} failed items...`);
        toast(`Retrying ${failedQueue.length} items...`, "info");

        const itemsToRetry = [...failedQueue];
        let successCount = 0;

        for (const item of itemsToRetry) {
            try {
                await sendToWebhook(item, 1);
                successCount++;
                
                // Add delay between batch sends
                await new Promise(resolve => setTimeout(resolve, CONFIG.BATCH_DELAY));
            } catch (error) {
                Logger.error(`Batch retry failed for: ${item.title}`, error);
            }
        }

        toast(`Batch complete: ${successCount}/${itemsToRetry.length} succeeded`, 
              successCount === itemsToRetry.length ? "success" : "warn");
    }

    // ============================================================
    // UNIVERSAL CLIP PARSER
    // ============================================================
    function parseClips(source) {
        if (!source) return [];
        if (Array.isArray(source)) return source;
        if (source.clips) return source.clips;
        if (source.result) return source.result;
        if (source.project?.clips) return source.project.clips;
        return [];
    }

    // ============================================================
    // CLIP HANDLER WITH VALIDATION
    // ============================================================
    function handleClips(rawClips) {
        const clips = Array.isArray(rawClips) ? rawClips : [];
        let processedCount = 0;

        clips.forEach(clip => {
            if (!clip) return;

            // Comprehensive validation
            const isValid = 
                clip.id &&
                clip.status === "complete" &&
                !clip.is_trashed &&
                clip.audio_url &&
                !sentIds[clip.id];

            if (!isValid) return;

            const payload = {
                id: clip.id,                                // Critical: Becomes video_id
                title: clip.title || `Suno Track ${clip.id}`,
                tags: clip.metadata?.tags || "Electronic",  // Critical: Guides the Llama Director
                audio_url: clip.audio_url,                  // Critical: Source audio
                duration: clip.metadata?.duration || 120,
                status: clip.status
                // Note: We intentionally OMIT image_url because Flux generates new art
            };

            sendToWebhook(payload).catch(err => {
                Logger.error(`Send failed for ${payload.title}`, err);
            });

            processedCount++;
        });

        if (processedCount > 0) {
            Logger.info(`Processed ${processedCount} new clips`);
        }
    }

    // ============================================================
    // HARDENED FETCH INTERCEPTOR
    // ============================================================
    const originalFetch = unsafeWindow.fetch;

    unsafeWindow.fetch = async function (...args) {
        let url = "";

        if (typeof args[0] === "string") url = args[0];
        else if (args[0]?.url) url = args[0].url;
        else if (args[0]?.toString) url = args[0].toString();

        // Silent tracker blackhole
        const blocked = ["stratovibe", "sentry", "segment", "agentio", "analytics"];
        if (blocked.some(b => url.includes(b))) {
            return new Response(
                JSON.stringify({ status: "blocked_by_god_mode", blocked: true }),
                { status: 200, headers: { "Content-Type": "application/json" } }
            );
        }

        const response = await originalFetch(...args);
        
        // Only process Suno API calls
        if (url.includes("suno.com/api") || url.includes("clerk.suno.com")) {
            const clone = response.clone();

            clone.json().then(data => {
                const clips = parseClips(data);
                if (clips.length) {
                    handleClips(clips);
                }
            }).catch(() => {
                // Silent fail for non-JSON responses
            });
        }

        return response;
     };

    // ============================================================
    // 🎛️ COMPLIANT MANUAL CONTROL HUD (Fixes "Missing ID/Name" Audit)
    // ============================================================
    function toggleControlPanel() {
        const PANEL_ID = "suno_god_mode_panel";
        const existing = document.getElementById(PANEL_ID);
        
        if (existing) {
            existing.remove();
            return;
        }

        const panel = document.createElement("div");
        panel.id = PANEL_ID;
        Object.assign(panel.style, {
            position: "fixed",
            bottom: "80px",
            right: "24px",
            width: "300px",
            background: "#0a0a0a",
            border: "1px solid #333",
            borderRadius: "8px",
            padding: "16px",
            zIndex: 999990,
            boxShadow: "0 4px 20px rgba(0,0,0,0.5)",
            fontFamily: "Inter, sans-serif"
        });

        // HEADER
        const header = document.createElement("h3");
        header.innerText = "⚡ Manual Trigger";
        header.style.color = "#fff";
        header.style.margin = "0 0 12px 0";
        header.style.fontSize = "14px";
        panel.appendChild(header);

        // FORM CONTAINER
        const form = document.createElement("div");
        
        // INPUT: Song ID (COMPLIANT)
        const inputGroup = document.createElement("div");
        inputGroup.style.marginBottom = "10px";
        
        const label = document.createElement("label");
        label.innerText = "Song UUID";
        label.htmlFor = "suno_manual_id"; // Links to ID
        label.style.display = "block";
        label.style.color = "#888";
        label.style.fontSize = "11px";
        label.style.marginBottom = "4px";

        const input = document.createElement("input");
        input.type = "text";
        input.id = "suno_manual_id";       // ✅ FIXED: Unique ID
        input.name = "suno_manual_id";     // ✅ FIXED: Unique Name
        input.placeholder = "e.g., a1b2c3d4-..."
        Object.assign(input.style, {
            width: "100%",
            background: "#1a1a1a",
            border: "1px solid #333",
            color: "#fff",
            padding: "8px",
            borderRadius: "4px",
            boxSizing: "border-box"
        });

        inputGroup.appendChild(label);
        inputGroup.appendChild(input);
        form.appendChild(inputGroup);

        // ACTION BUTTON
        const btn = document.createElement("button");
        btn.id = "suno_trigger_btn";       // ✅ FIXED
        btn.name = "suno_trigger_btn";     // ✅ FIXED
        btn.innerText = "PUSH TO PIPELINE";
        Object.assign(btn.style, {
            width: "100%",
            background: "#fff",
            color: "#000",
            border: "none",
            padding: "8px",
            borderRadius: "4px",
            fontWeight: "bold",
            cursor: "pointer",
            marginTop: "8px"
        });

        // LOGIC
        btn.onclick = () => {
            const id = document.getElementById("suno_manual_id").value.trim();
            if (!id) {
                toast("Enter a Song ID", "warn");
                return;
            }
            // Mock a clip object for the handler
            handleClips([{
                id: id,
                title: "Manual Override",
                audio_url: `https://cdn1.suno.ai/${id}.mp3`,
                image_url: `https://cdn1.suno.ai/image_${id}.png`,
                status: "complete",
                metadata: { tags: "manual_trigger" }
            }]);
            toast(`Manually Pushed: ${id.slice(0,8)}...`, "success");
        };

        form.appendChild(btn);
        panel.appendChild(form);
        document.body.appendChild(panel);
    }

    // ============================================================
    // MENU COMMANDS
    // ============================================================
    GM_registerMenuCommand("⚡ Force Rescan Feed", () => {
        toast("Rescanning Suno feed...", "info");
        fetch("https://suno.com/api/feed?page=1").catch(() => {});
    });

    GM_registerMenuCommand("🔄 Retry Failed Queue", retryFailedQueue);

    GM_registerMenuCommand("🧹 Clear Sent Cache", () => {
        if (confirm("⚠️  Clear sent history? ALL songs will be re-sent on next detection.")) {
            GM_setValue(STORAGE_KEYS.SENT_IDS, {});
            sentIds = {};
            toast("Cache cleared - fresh start", "success");
        }
    });

    GM_registerMenuCommand("📊 Show Statistics", showStats);

    GM_registerMenuCommand("🏥 Health Check", () => {
        performHealthCheck().then(healthy => {
            if (!healthy) {
                toast("Health check failed - check console", "error");
            }
        });
    });

    GM_registerMenuCommand("💾 Export Failed Queue", () => {
        const dataStr = JSON.stringify(failedQueue, null, 2);
        const dataBlob = new Blob([dataStr], { type: "application/json" });
        const url = URL.createObjectURL(dataBlob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `suno_failed_queue_${Date.now()}.json`;
        link.click();
        URL.revokeObjectURL(url);
        toast("Failed queue exported", "success");
    });

    GM_registerMenuCommand("🎛️ Toggle Control Panel", toggleControlPanel);

    // ============================================================
    // INITIALIZATION
    // ============================================================
    Logger.success("GOD MODE v7.0 Active");
    Logger.info("Configuration:", CONFIG);
    Logger.info("Stats:", stats);
    
    if (failedQueue.length > 0) {
        Logger.warn(`${failedQueue.length} items in failed queue`);
    }

    // Perform initial health check
    setTimeout(performHealthCheck, 2000);

    // Display startup notification
    toast("Suno Bridge v7.0 Online", "success", 2500);
})();
