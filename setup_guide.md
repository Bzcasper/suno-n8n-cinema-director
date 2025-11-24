# Suno Music Video Pipeline - Production Setup Guide

## 🎯 Overview

This guide walks you through setting up a complete, production-ready pipeline that:
1. Captures songs from Suno.com
2. Generates high-quality looping music videos using AI
3. Organizes everything in Google Drive with YouTube-ready metadata

---

## 📋 Prerequisites

### Required Accounts & Services
- [x] **Google Cloud Platform** account (for Google Drive API)
- [x] **Modal Labs** account (for video generation)
- [x] **n8n** instance (self-hosted or cloud)
- [x] **Tampermonkey** browser extension

### Required Knowledge
- Basic understanding of REST APIs
- Familiarity with n8n workflows
- Basic Python knowledge (for Modal customization)

---

## 🚀 Part 1: Modal Labs Setup

### 1.1 Install Modal CLI

```bash
pip install modal
modal setup
```

### 1.2 Create Modal Secrets

```bash
# Create a secret for your API tokens (if needed)
modal secret create suno-video-secrets \
  OPENAI_API_KEY=your_key_here \
  OTHER_SECRET=value
```

### 1.3 Deploy Video Generator

```bash
# Save the modal_video_generator.py file
# Then deploy to Modal
modal deploy modal_video_generator.py

# Note the endpoint URL - you'll need this for n8n
# Example: https://your-username--suno-video-generator-generate-music-video.modal.run
```

### 1.4 Test the Deployment

```bash
# Run a test locally
modal run modal_video_generator.py

# Check the logs
modal app logs suno-video-generator
```

---

## 🔧 Part 2: Google Drive Setup

### 2.1 Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project: "Suno Video Pipeline"
3. Enable Google Drive API:
   - Go to "APIs & Services" → "Library"
   - Search "Google Drive API"
   - Click "Enable"

### 2.2 Create Service Account

1. Go to "IAM & Admin" → "Service Accounts"
2. Click "Create Service Account"
3. Name it: `suno-pipeline-service`
4. Grant role: "Editor"
5. Click "Create Key" → JSON
6. **Save this JSON file securely** - you'll need it for n8n

### 2.3 Setup Drive Folder Structure

1. Create a folder in your Google Drive: "Suno"
2. Share this folder with the service account email (from the JSON file)
3. Grant "Editor" permissions
4. Note the folder ID from the URL: `https://drive.google.com/drive/folders/FOLDER_ID_HERE`

**Recommended Structure:**
```
Suno/
├── 2025-01/
│   ├── electronic/
│   ├── rock/
│   └── ambient/
├── 2025-02/
│   └── ...
```

---

## ⚙️ Part 3: n8n Workflow Setup

### 3.1 Import Workflow

1. Open your n8n instance
2. Click "+" → "Import from File"
3. Upload `n8n_production_workflow.json`

### 3.2 Configure Credentials

#### Google Service Account
1. Go to "Credentials" in n8n
2. Add "Google Service Account"
3. Upload the JSON key from Step 2.2
4. Test connection

#### Modal Labs API
1. Get your Modal token: `modal token new`
2. In n8n, create "HTTP Header Auth" credential
3. Header: `Authorization`
4. Value: `Bearer YOUR_MODAL_TOKEN`

### 3.3 Update Workflow Settings

**In the "Generate Video (Modal)" node:**
```javascript
URL: https://YOUR_MODAL_URL.modal.run
```

**In "Create Drive Folder" node:**
```javascript
Parent Folder ID: YOUR_FOLDER_ID_FROM_STEP_2.3
```

### 3.4 Activate Webhook

1. Open the "Suno Webhook" node
2. Click "Test URL" to get your webhook URL
3. Copy this URL - you'll need it for Tampermonkey
4. Click "Production URL" to activate it

---

## 🔌 Part 4: Tampermonkey Script Installation

### 4.1 Install Tampermonkey

- **Chrome/Edge**: [Chrome Web Store](https://chrome.google.com/webstore/detail/tampermonkey/)
- **Firefox**: [Firefox Add-ons](https://addons.mozilla.org/en-US/firefox/addon/tampermonkey/)

### 4.2 Install Script

1. Click Tampermonkey icon → "Create new script"
2. Delete all existing code
3. Paste the entire `enhanced_suno_bridge.user.js` content
4. **IMPORTANT**: Update line 23 with your n8n webhook URL:
   ```javascript
   WEBHOOK_URL: "YOUR_N8N_WEBHOOK_URL_HERE",
   ```
5. Save (Ctrl/Cmd + S)

### 4.3 Verify Installation

1. Go to [suno.com](https://suno.com)
2. You should see a green toast: "Suno Bridge v7.0 Online"
3. Check browser console for confirmation logs

---

## ✅ Part 5: Testing the Pipeline

### 5.1 Generate a Test Song

1. Go to Suno.com
2. Create a new song
3. Wait for it to complete
4. Watch for the toast notification: "Uploading: [Song Title]"

### 5.2 Monitor n8n Execution

1. Go to n8n → "Executions"
2. You should see a new execution running
3. Watch the workflow progress through each node
4. Check for any errors

### 5.3 Verify Google Drive

1. Open your "Suno" folder in Google Drive
2. Navigate to the date-based subfolder (e.g., `2025-01/electronic/`)
3. Verify these files exist:
   - `song_name.mp4` (video)
   - `song_name.mp3` (audio)
   - `song_name.jpg` (cover)
   - `song_name_metadata.txt` (YouTube description)

### 5.4 Check Video Quality

1. Download the MP4 file
2. Verify:
   - Resolution: 1920x1080
   - Audio quality: 320kbps
   - Video bitrate: 8000k
   - No corruption or glitches
   - Smooth looping effect

---

## 🐛 Part 6: Troubleshooting

### Issue: Webhook Not Receiving Data

**Symptoms:** No toast notifications on Suno.com

**Solutions:**
1. Check Tampermonkey console for errors
2. Verify webhook URL is correct in script
3. Test webhook manually:
   ```bash
   curl -X POST YOUR_WEBHOOK_URL \
     -H "Content-Type: application/json" \
     -d '{"health_check": true}'
   ```

### Issue: Modal Video Generation Fails

**Symptoms:** n8n execution stops at Modal node

**Solutions:**
1. Check Modal logs: `modal app logs suno-video-generator`
2. Verify Modal deployment is active
3. Test Modal endpoint directly:
   ```bash
   curl -X POST YOUR_MODAL_URL \
     -H "Content-Type: application/json" \
     -d '{"audio_url": "TEST_URL", "video_id": "test123"}'
   ```

### Issue: Google Drive Upload Fails

**Symptoms:** n8n error at Drive upload nodes

**Solutions:**
1. Verify service account has permissions on folder
2. Check service account JSON credentials in n8n
3. Ensure folder ID is correct
4. Test with a manual file upload in n8n

### Issue: Videos Not YouTube-Ready

**Symptoms:** YouTube rejects uploaded videos

**Solutions:**
1. Verify video specs meet YouTube requirements:
   - Max resolution: 1920x1080
   - Format: MP4 (H.264 + AAC)
   - Max bitrate: 8000k
2. Re-encode if necessary using ffmpeg:
   ```bash
   ffmpeg -i input.mp4 -c:v libx264 -preset slow \
     -b:v 8000k -c:a aac -b:a 320k output.mp4
   ```

---

## 📊 Part 7: Monitoring & Maintenance

### 7.1 Tampermonkey Menu Commands

Access via Tampermonkey icon → "Suno-to-n8n Bridge" menu:

- **⚡ Force Rescan Feed**: Manually trigger song detection
- **🔄 Retry Failed Queue**: Retry all failed uploads
- **🧹 Clear Sent Cache**: Reset history (use with caution)
- **📊 Show Statistics**: View upload stats
- **🏥 Health Check**: Test webhook connectivity
- **💾 Export Failed Queue**: Download failed items as JSON

### 7.2 n8n Monitoring

**Set up email alerts for failures:**
1. Add "Send Email" node after error nodes
2. Configure SMTP credentials
3. Set up alert template

**Monitor execution history:**
- Check "Executions" tab daily
- Look for patterns in failures
- Optimize workflow based on bottlenecks

### 7.3 Modal Monitoring

```bash
# View recent logs
modal app logs suno-video-generator --tail

# Check function stats
modal app list

# Monitor costs
modal billing list
```

### 7.4 Storage Management

**Automated cleanup script for old files:**
```python
# cleanup_old_videos.py
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta

# Delete videos older than 90 days
cutoff_date = datetime.now() - timedelta(days=90)
# Implementation details...
```

---

## 🚀 Part 8: Performance Optimization

### 8.1 Modal Optimization

**Increase concurrency for batch processing:**
```python
@app.function(
    image=image,
    timeout=600,
    memory=4096,
    concurrency_limit=10  # Process 10 videos simultaneously
)
```

**Use GPU for faster rendering (optional):**
```python
@app.function(
    image=image,
    gpu="T4",  # Add GPU for faster video processing
    timeout=300
)
```

### 8.2 n8n Optimization

**Enable batching:**
1. Add "Batch" node before Modal call
2. Set batch size: 5 videos
3. Process in parallel

**Cache Drive folder IDs:**
1. Use n8n's memory store
2. Avoid recreating existing folders
3. Speed up uploads by 2-3x

### 8.3 Network Optimization

**Use CDN for faster downloads:**
1. Cache audio/images in Cloudflare R2
2. Serve from edge locations
3. Reduce Modal processing time

---

## 📝 Part 9: Customization Guide

### 9.1 Customize Video Generation

**Change video style in `modal_video_generator.py`:**

```python
# Add custom effects
from moviepy.video.fx import fadein, fadeout, resize

# Apply effects to clips
clip = clip.fx(fadein, 1).fx(fadeout, 1)

# Add custom overlays
logo = ImageClip("logo.png").set_duration(clip.duration)
final = CompositeVideoClip([clip, logo.set_position(("right", "bottom"))])
```

**Change video resolution:**
```python
target_size = (3840, 2160)  # 4K resolution
```

**Add custom music visualizations:**
```python
# Use pydub for audio analysis
from pydub import AudioSegment
from pydub.utils import make_chunks

# Implement waveform or spectrum visualization
```

### 9.2 Customize Drive Organization

**Update folder structure in n8n Code node:**

```javascript
// Organize by artist name (extracted from tags)
const artist = songData.tags.split('-')[0].trim();
const drive_folder_path = `Suno/Artists/${artist}/${dateFolder}`;

// Or organize by BPM ranges
const bpm = songData.metadata?.bpm || 120;
const bpm_range = bpm < 100 ? "slow" : bpm < 140 ? "medium" : "fast";
const drive_folder_path = `Suno/BPM/${bpm_range}/${dateFolder}`;
```

### 9.3 Add YouTube Auto-Upload

**Extend n8n workflow with YouTube API:**

1. Enable YouTube Data API in Google Cloud
2. Add OAuth2 credentials for YouTube
3. Add "YouTube Upload" node after Drive upload
4. Auto-fill metadata from generated description

---

## 🎓 Part 10: Advanced Features

### 10.1 AI-Generated Video Descriptions

**Add GPT-4 node in n8n before Modal:**

```javascript
// Call OpenAI API to generate creative description
const prompt = `Write a YouTube description for this AI-generated song:
Title: ${songData.title}
Genre: ${songData.tags}
Prompt: ${songData.prompt}

Include hashtags, creative commentary, and call-to-action.`;
```

### 10.2 Automatic Playlist Creation

**Create themed playlists in Drive:**

1. Add "Aggregate" node to collect songs by genre
2. Once you have 10+ songs, create a playlist JSON
3. Generate playlist cover art with DALL-E
4. Upload to dedicated "Playlists" folder

### 10.3 Analytics Dashboard

**Track performance metrics:**

1. Send stats to Google Sheets
2. Create real-time dashboard with charts
3. Monitor:
   - Songs processed per day
   - Video generation time
   - Storage usage
   - Most popular genres

---

## 🔐 Security Best Practices

### Critical Security Measures

1. **Never commit credentials to Git**
   - Use `.env` files
   - Add to `.gitignore`

2. **Rotate service account keys quarterly**
   ```bash
   gcloud iam service-accounts keys create new-key.json \
     --iam-account=suno-pipeline@project.iam.gserviceaccount.com
   ```

3. **Enable Google Drive audit logging**
   - Monitor for unauthorized access
   - Set up alerts for suspicious activity

4. **Use Modal secrets for sensitive data**
   ```bash
   modal secret create production-secrets \
     API_KEY=xxx \
     WEBHOOK_SECRET=yyy
   ```

5. **Implement webhook authentication**
   ```javascript
   // In n8n, add validation node
   if (headers['x-webhook-secret'] !== process.env.WEBHOOK_SECRET) {
     return { error: 'Unauthorized' };
   }
   ```

---

## 📈 Scaling Considerations

### When You Hit 100+ Songs/Day

1. **Upgrade Modal plan** for higher concurrency
2. **Implement queue system** with Redis
3. **Use multiple n8n workers** for parallel processing
4. **Consider dedicated GPU instances** for faster rendering
5. **Implement CDN caching** for frequently accessed videos

### Storage Management at Scale

**Estimated costs at scale:**
- 100 songs/day = ~3TB/month
- Google Drive: $9.99/100GB → ~$300/month
- Consider Google Cloud Storage instead: ~$20/month

**Migration strategy:**
```bash
# Move old videos to cold storage
gsutil -m cp -r gs://hot-bucket/* gs://cold-bucket/
```

---

## 🎉 Conclusion

You now have a fully functional, production-ready pipeline that:
- ✅ Automatically captures Suno songs
- ✅ Generates high-quality music videos
- ✅ Organizes everything in Google Drive
- ✅ Produces YouTube-ready content

### Next Steps

1. **Monitor the first 10 videos** closely for any issues
2. **Fine-tune video generation** parameters for your style
3. **Set up automated backups** of Google Drive content
4. **Create a YouTube channel** and start uploading!

### Support & Resources

- **Modal Docs**: https://modal.com/docs
- **n8n Docs**: https://docs.n8n.io
- **Google Drive API**: https://developers.google.com/drive

---

## 🐛 Support

If you encounter issues:
1. Check the troubleshooting section above
2. Review logs in all three systems (Tampermonkey, n8n, Modal)
3. Test each component individually
4. Verify all credentials are correct

**Happy video generating! 🎵🎬**
