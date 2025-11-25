# Production Setup Checklist

## 📋 Pre-Deployment Checklist

### Phase 1: Account Setup
- [ ] Google Cloud Platform account created
- [ ] Modal Labs account created (modallab.com)
- [ ] n8n instance deployed (self-hosted or cloud.n8n.io)
- [ ] Tampermonkey installed in browser

### Phase 2: Google Cloud Configuration
- [ ] Google Cloud project created
- [ ] Google Drive API enabled
- [ ] Service account created
- [ ] Service account JSON key downloaded
- [ ] Main "Suno" folder created in Drive
- [ ] Service account granted Editor permissions on folder
- [ ] Folder ID copied from URL

**Folder ID**: `___________________________`

### Phase 3: Modal Labs Setup
- [ ] Modal CLI installed: `pip install modal`
- [ ] Modal authenticated: `modal setup`
- [ ] `modal_video_gen.py` saved locally
- [ ] Secrets created (if needed): `modal secret create suno-video-secrets`
- [ ] Script deployed: `modal deploy modal_video_gen.py`
- [ ] Endpoint URL copied

**Modal Endpoint**: `___________________________`

### Phase 4: n8n Configuration
- [ ] Workflow JSON imported into n8n
- [ ] Google Service Account credential added
- [ ] Service account JSON uploaded to n8n
- [ ] Modal Labs HTTP Auth credential created
- [ ] Modal bearer token added to credential
- [ ] Webhook URL activated
- [ ] Test execution successful

**n8n Webhook URL**: `___________________________`

### Phase 5: Tampermonkey Setup
- [ ] Script copied to new Tampermonkey script
- [ ] Webhook URL updated in script (line 23)
- [ ] Script saved and active
- [ ] Tested on suno.com (green toast visible)
- [ ] Browser console shows no errors

---

## 🔧 Configuration Values

### Environment Variables

```bash
# Google Cloud
GOOGLE_PROJECT_ID=________________
GOOGLE_SERVICE_ACCOUNT_EMAIL=________________
GOOGLE_DRIVE_FOLDER_ID=________________

# Modal Labs
MODAL_TOKEN=________________
MODAL_ENDPOINT_URL=________________

# n8n
N8N_WEBHOOK_URL=________________
N8N_WEBHOOK_SECRET=________________  # Optional but recommended
```

### Tampermonkey Configuration

```javascript
// File: enhanced_suno_bridge.user.js
// Line 23 - Update this:
WEBHOOK_URL: "YOUR_N8N_WEBHOOK_URL_HERE"

// Optional: Adjust these if needed
MAX_RETRIES: 3                    // Number of retry attempts
RETRY_DELAY_BASE: 1000           // Base delay in ms
TIMEOUT: 15000                   // Request timeout in ms
BATCH_DELAY: 2000                // Delay between batch sends
HEALTH_CHECK_INTERVAL: 300000    // Health check every 5 minutes
MAX_QUEUE_SIZE: 50               // Max items in failed queue
```

### n8n Workflow Configuration

**Nodes to Update:**

1. **Generate Video (Modal)** node
   - URL: `YOUR_MODAL_ENDPOINT`
   - Auth: HTTP Header Auth (Bearer token)

2. **Create Drive Folder** node
   - Parent folder ID: `YOUR_FOLDER_ID`
   - Credentials: Google Service Account

3. **All Google Drive nodes**
   - Credentials: Same service account

### Modal Configuration

```python
# File: modal_video_gen.py

# Video quality settings (lines ~100-110)
target_size = (1920, 1080)        # Video resolution
fps = 30                          # Frames per second
bitrate = '8000k'                 # Video bitrate
audio_bitrate = '320k'            # Audio bitrate
preset = 'slow'                   # Encoding preset (slow = higher quality)

# Resource allocation (lines ~47-52)
timeout = 600                     # Max processing time (seconds)
memory = 4096                     # RAM in MB
concurrency_limit = 5             # Parallel videos
```

---

## ✅ Post-Deployment Testing

### Test 1: End-to-End Pipeline
- [ ] Go to suno.com
- [ ] Generate a test song (or use existing)
- [ ] Wait for completion
- [ ] Verify toast notification appears
- [ ] Check n8n execution dashboard
- [ ] Verify all nodes executed successfully
- [ ] Check Google Drive for all 4 files:
  - [ ] MP4 video
  - [ ] MP3 audio
  - [ ] JPG cover
  - [ ] TXT metadata

### Test 2: Error Recovery
- [ ] Temporarily break webhook URL in Tampermonkey
- [ ] Generate a song
- [ ] Verify it enters failed queue
- [ ] Fix webhook URL
- [ ] Use "Retry Failed Queue" menu command
- [ ] Verify song uploads successfully

### Test 3: Quality Verification
- [ ] Download generated MP4
- [ ] Check video properties:
  - [ ] Resolution: 1920x1080
  - [ ] Duration matches audio
  - [ ] Audio clear and synced
  - [ ] No corruption or artifacts
  - [ ] Text overlays readable
  - [ ] Smooth looping effect

### Test 4: Scale Test
- [ ] Generate 5 songs in quick succession
- [ ] Verify all are captured
- [ ] Check for any rate limiting
- [ ] Verify proper folder organization
- [ ] Check Modal logs for performance

---

## 🚨 Common Issues & Quick Fixes

| Issue | Quick Fix |
|-------|-----------|
| No toast notification | Check Tampermonkey console, verify script is active |
| Webhook 404 error | Activate webhook in n8n (click "Production URL") |
| Modal timeout | Increase timeout value in n8n node settings |
| Drive permission error | Re-share folder with service account email |
| Video generation fails | Check Modal logs: `modal app logs suno-video-generator` |
| Duplicate uploads | Don't clear sent cache unless intentional |

---

## 📊 Monitoring Dashboard

### Daily Checks
- [ ] Review n8n execution history
- [ ] Check Tampermonkey statistics (📊 menu)
- [ ] Monitor Google Drive storage usage
- [ ] Review Modal usage/costs

### Weekly Checks
- [ ] Export failed queue for analysis
- [ ] Review video quality samples
- [ ] Check for any patterns in failures
- [ ] Optimize workflow based on bottlenecks

### Monthly Checks
- [ ] Rotate service account keys
- [ ] Review and archive old videos
- [ ] Update dependencies:
  - [ ] `pip install --upgrade modal`
  - [ ] Update Tampermonkey script if new version
  - [ ] Update n8n to latest version
- [ ] Review costs and optimize

---

## 🎯 Performance Metrics

### Target KPIs
- **Upload success rate**: >95%
- **Average processing time**: <5 minutes per song
- **Video quality score**: >4/5 (subjective review)
- **Storage cost per song**: <$0.10
- **Modal processing cost**: <$0.20 per video

### Tracking Template

```
Date: ___________
Songs processed: ___________
Successful uploads: ___________
Failed uploads: ___________
Average processing time: ___________
Storage used: ___________
Modal costs: ___________
Notes: _______________________________________
```

---

## 🔐 Security Checklist

- [ ] Service account JSON stored securely (not in Git)
- [ ] n8n webhook uses HTTPS
- [ ] Modal secrets configured for sensitive data
- [ ] Google Drive folder not publicly shared
- [ ] Tampermonkey script doesn't log sensitive data
- [ ] Regular credential rotation scheduled
- [ ] Audit logs enabled in Google Cloud
- [ ] Two-factor authentication enabled on all accounts

---

## 📞 Support Contacts

**Modal Support**: support@modal.com  
**n8n Community**: https://community.n8n.io  
**Google Cloud Support**: https://cloud.google.com/support

---

## 🎓 Additional Resources

### Documentation
- [Modal Video Tutorial](https://modal.com/docs/examples/video_processing)
- [n8n Google Drive Node](https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.googledrive/)
- [MoviePy Documentation](https://zulko.github.io/moviepy/)

### Video Optimization
- [FFmpeg Guide](https://trac.ffmpeg.org/wiki)
- [YouTube Upload Requirements](https://support.google.com/youtube/answer/1722171)
- [Video Compression Best Practices](https://docs.modal.com/guide/video-compression)

### Community
- [r/n8n on Reddit](https://reddit.com/r/n8n)
- [Modal Discord](https://modal.com/discord)
- [Suno Discord](https://discord.gg/suno)

---

## 🎉 Ready for Production?

Final checklist before going live:
- [ ] All 5 phases completed
- [ ] All 4 tests passed
- [ ] Security checklist complete
- [ ] Monitoring dashboard set up
- [ ] Backup strategy in place
- [ ] Documentation reviewed
- [ ] Team trained (if applicable)

**If all boxes are checked, you're ready to go! 🚀**

---

**Version**: 1.0  
**Last Updated**: November 2025  
**Status**: ⬜ Not Started | 🟨 In Progress | ✅ Complete
