// ==UserScript==
// @name         Suno-to-n8n Bridge (God Mode v7.1 - FIXED Double Nesting)
// @namespace    http://tampermonkey.net/
// @version      7.1
// @description  CRITICAL FIX: Removed double body nesting, sends flat structure to n8n
// @author       Robert Casper (Fixed by Expert Software Development Assistant)
// @match        https://suno.com/*
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_registerMenuCommand
// @grant        unsafeWindow
// @run-at       document-start
// ==/UserScript==

;(function () {
  'use strict'

  // ============================================================
  // CONFIGURATION
  // ============================================================
  const WEBHOOK_URL = 'https://n8n-gszggfatjq-uc.a.run.app/webhook/suno-trigger'
  const MAX_RETRIES = 3
  const SENT_IDS_KEY = 'suno_sent_ids_v7'
  const DEBUG_MODE = true

  let sentIds = GM_getValue(SENT_IDS_KEY, {})

  // ============================================================
  // DEBUG LOGGER
  // ============================================================
  function log(msg, level = 'info') {
    if (!DEBUG_MODE && level === 'debug') return

    const prefix = '[Suno Bridge v7.1]'
    const styles = {
      info: 'color: #00eaff',
      success: 'color: #00ff40',
      error: 'color: #ff003c',
      warn: 'color: #ffcc00',
      debug: 'color: #888888',
    }

    console.log(`%c${prefix} ${msg}`, styles[level] || styles.info)
  }

  // ============================================================
  // NEON HUD: SAFE TOAST SYSTEM
  // ============================================================
  function toast(msg, type = 'info', duration = 3500) {
    if (!document.body) {
      document.addEventListener('DOMContentLoaded', () => toast(msg, type, duration))
      return
    }

    const palette = {
      info: { c: '#00eaff' },
      success: { c: '#00ff40' },
      error: { c: '#ff003c' },
      warn: { c: '#ffcc00' },
    }

    const color = palette[type]?.c || '#00eaff'

    const el = document.createElement('div')
    el.innerText = `>> ${msg}`

    Object.assign(el.style, {
      position: 'fixed',
      bottom: '24px',
      right: '24px',
      padding: '12px 20px',
      background: '#050505',
      border: `1px solid ${color}`,
      borderLeft: `4px solid ${color}`,
      color: color,
      fontFamily: 'Fira Code, monospace',
      fontSize: '12px',
      letterSpacing: '0.5px',
      textTransform: 'uppercase',
      boxShadow: `0 0 12px ${color}55`,
      opacity: '0',
      transform: 'translateY(20px)',
      zIndex: 999999,
      pointerEvents: 'none',
      transition: 'all .25s ease-out',
    })

    document.body.appendChild(el)
    requestAnimationFrame(() => {
      el.style.opacity = '1'
      el.style.transform = 'translateY(0)'
    })

    setTimeout(() => {
      el.style.opacity = '0'
      el.style.transform = 'translateY(10px)'
      setTimeout(() => el.remove(), 300)
    }, duration)
  }

  // ============================================================
  // RETRY ENGINE WITH CORRECT STRUCTURE (CRITICAL FIX)
  // ============================================================
  function sendToWebhook(clipData, attempt = 1) {
    if (sentIds[clipData.id]) {
      log(`Skipping duplicate: ${clipData.id}`, 'debug')
      return
    }

    // CRITICAL FIX: Send FLAT structure - n8n webhook will wrap it in body
    // DO NOT wrap in body ourselves to avoid double nesting
    const payload = {
      id: clipData.id,
      title: clipData.title,
      audio_url: clipData.audio_url,
      image_url: clipData.image_url,
      video_url: clipData.video_url,
      prompt: clipData.prompt,
      tags: clipData.tags,
      model: clipData.model,
      duration: clipData.duration,
      created_at: clipData.created_at,
      source: clipData.source,
    }

    const retry = attempt > 1
    const logPrefix = retry ? `[Retry ${attempt}/${MAX_RETRIES}]` : `[New]`

    log(`${logPrefix} Sending: ${clipData.title} (${clipData.id})`, retry ? 'warn' : 'info')

    if (DEBUG_MODE) {
      console.log('Full payload (flat structure):', JSON.stringify(payload, null, 2))
    }

    if (!retry) toast(`Uploading: ${clipData.title}`, 'info')

    GM_xmlhttpRequest({
      method: 'POST',
      url: WEBHOOK_URL,
      headers: { 'Content-Type': 'application/json' },
      data: JSON.stringify(payload),
      timeout: 15000,

      onload: (res) => {
        log(`Response status: ${res.status}`, 'debug')

        if (res.status >= 200 && res.status < 300) {
          sentIds[clipData.id] = {
            title: clipData.title,
            sentAt: new Date().toISOString(),
          }
          GM_setValue(SENT_IDS_KEY, sentIds)

          log(`✓ Success: ${clipData.title}`, 'success')
          toast(`Pipeline Success: ${clipData.title}`, 'success')
        } else {
          log(`✗ HTTP ${res.status}: ${res.responseText}`, 'error')
          handleSendError(res.status, clipData, attempt)
        }
      },

      onerror: (err) => {
        log(`✗ Network Error: ${err.error || 'Unknown'}`, 'error')
        handleSendError('NETWORK', clipData, attempt)
      },

      ontimeout: () => {
        log(`✗ Timeout after 15s`, 'error')
        handleSendError('TIMEOUT', clipData, attempt)
      },
    })
  }

  function handleSendError(code, clipData, attempt) {
    if (attempt < MAX_RETRIES) {
      const wait = 1000 * Math.pow(2, attempt)
      log(`Error ${code} — Retrying in ${wait}ms`, 'warn')
      setTimeout(() => sendToWebhook(clipData, attempt + 1), wait)
    } else {
      log(`✗ FAILED after ${MAX_RETRIES} attempts: ${clipData.title}`, 'error')
      toast(`Failed: ${clipData.title} (${code})`, 'error', 5000)
    }
  }

  // ============================================================
  // ENHANCED CLIP VALIDATOR
  // ============================================================
  function isValidClip(clip) {
    if (!clip || typeof clip !== 'object') {
      return false
    }

    const hasRequiredFields =
      clip.id && clip.audio_url && clip.status === 'complete' && !clip.is_trashed

    if (!hasRequiredFields) {
      log(`Invalid clip: Missing required fields or not complete`, 'debug')
      return false
    }

    if (sentIds[clip.id]) {
      log(`Skipping: Already sent ${clip.id}`, 'debug')
      return false
    }

    return true
  }

  // ============================================================
  // UNIVERSAL CLIP PARSER (ENHANCED)
  // ============================================================
  function parseClips(source) {
    if (!source) return []

    if (Array.isArray(source)) return source

    const paths = [
      source.clips,
      source.result,
      source.data?.clips,
      source.data,
      source.project?.clips,
      source.response?.clips,
    ]

    for (const path of paths) {
      if (Array.isArray(path)) return path
    }

    if (source.id && source.audio_url) return [source]

    return []
  }

  // ============================================================
  // CLIP HANDLER WITH ENHANCED LOGGING
  // ============================================================
  function handleClips(rawClips) {
    const clips = parseClips(rawClips)

    if (clips.length === 0) {
      log('No clips found in response', 'debug')
      return
    }

    log(`Processing ${clips.length} clip(s)`, 'info')

    let sentCount = 0
    let skippedCount = 0

    clips.forEach((clip) => {
      if (!isValidClip(clip)) {
        skippedCount++
        return
      }

      const clipData = {
        id: clip.id,
        title: clip.title || clip.display_name || 'Untitled_Track',
        audio_url: clip.audio_url,
        image_url: clip.image_url || clip.image_large_url || '',
        video_url: clip.video_url || '',
        prompt: clip.metadata?.prompt || clip.gpt_description_prompt || '',
        tags: clip.metadata?.tags || clip.metadata?.gpt_description_prompt || '',
        model: clip.major_model_version || clip.model_name || 'unknown',
        duration: clip.metadata?.duration || clip.duration || 0,
        created_at: clip.created_at || new Date().toISOString(),
        source: 'suno_god_mode_v7_1',
      }

      log(`→ Queueing: ${clipData.title}`, 'info')
      sendToWebhook(clipData)
      sentCount++
    })

    log(`Batch complete: ${sentCount} sent, ${skippedCount} skipped`, 'success')
  }

  // ============================================================
  // FETCH INTERCEPTOR (HARDENED + ENHANCED)
  // ============================================================
  const originalFetch = unsafeWindow.fetch

  unsafeWindow.fetch = async function (...args) {
    let url = ''

    if (typeof args[0] === 'string') url = args[0]
    else if (args[0]?.url) url = args[0].url
    else if (args[0]?.toString) url = args[0].toString()

    const blocked = ['stratovibe', 'sentry', 'segment', 'agentio', 'mixpanel', 'amplitude']
    if (blocked.some((b) => url.includes(b))) {
      log(`Blocked tracker: ${url}`, 'debug')
      return new Response(JSON.stringify({ status: 'blocked_by_god_mode' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }

    const response = await originalFetch(...args)

    if (!url.includes('suno.com/api') && !url.includes('cdn.suno')) {
      return response
    }

    log(`Intercepted: ${url}`, 'debug')
    const clone = response.clone()

    clone
      .json()
      .then((data) => {
        const clips = parseClips(data)
        if (clips.length) {
          log(`Found ${clips.length} clips in API response`, 'info')
          handleClips(clips)
        }
      })
      .catch((err) => {
        log(`Parse error: ${err.message}`, 'debug')
      })

    return response
  }

  // ============================================================
  // DOM OBSERVER FOR DYNAMICALLY LOADED CONTENT
  // ============================================================
  function observeDOMForClips() {
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType === 1) {
            const fiber = node._reactFiber || node._reactInternalFiber
            if (fiber?.memoizedProps?.clip) {
              handleClips([fiber.memoizedProps.clip])
            }
          }
        })
      })
    })

    if (document.body) {
      observer.observe(document.body, {
        childList: true,
        subtree: true,
      })
      log('DOM observer active', 'debug')
    } else {
      document.addEventListener('DOMContentLoaded', () => {
        observer.observe(document.body, {
          childList: true,
          subtree: true,
        })
        log('DOM observer active', 'debug')
      })
    }
  }

  // ============================================================
  // MENU COMMANDS
  // ============================================================
  GM_registerMenuCommand('⚡ Force Rescan Feed', () => {
    toast('Rescanning feed...', 'warn')
    log('Manual rescan triggered', 'info')
    fetch('https://suno.com/api/feed?page=1')
      .then(() => log('Rescan complete', 'success'))
      .catch((err) => log(`Rescan error: ${err}`, 'error'))
  })

  GM_registerMenuCommand('🧹 Clear Sent Cache', () => {
    if (confirm('Clear history? ALL songs will resend.')) {
      GM_setValue(SENT_IDS_KEY, {})
      sentIds = {}
      toast('Cache Cleared', 'success')
      log('Sent cache cleared', 'info')
    }
  })

  GM_registerMenuCommand('📊 Show Statistics', () => {
    const count = Object.keys(sentIds).length
    const recent = Object.entries(sentIds)
      .slice(-5)
      .map(([id, data]) => `${data.title} (${data.sentAt})`)
      .join('\n')

    alert(`Total Sent: ${count}\n\nRecent:\n${recent || 'None'}`)
  })

  GM_registerMenuCommand('🐛 Toggle Debug Mode', () => {
    const newMode = !DEBUG_MODE
    window.SUNO_DEBUG = newMode
    toast(`Debug: ${newMode ? 'ON' : 'OFF'}`, 'info')
  })

  // ============================================================
  // INITIALIZATION
  // ============================================================
  log('='.repeat(60), 'info')
  log('GOD MODE v7.1 ACTIVE (Fixed Double Nesting)', 'success')
  log(`Webhook: ${WEBHOOK_URL}`, 'info')
  log(`Cached IDs: ${Object.keys(sentIds).length}`, 'info')
  log(`Debug Mode: ${DEBUG_MODE ? 'ON' : 'OFF'}`, 'info')
  log('='.repeat(60), 'info')

  toast('System Online v7.1', 'success', 2500)

  observeDOMForClips()

  setInterval(() => {
    log(`Health check: ${Object.keys(sentIds).length} clips sent`, 'debug')
  }, 30000)
})()
