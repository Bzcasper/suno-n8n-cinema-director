# AGENTS.md - Suno Music Video Pipeline

## Build/Lint/Test Commands

### Modal Labs Deployment
- **Deploy to production**: `modal deploy modal_video_gen.py`
- **Local testing**: `modal run modal_video_gen.py`
- **Check logs**: `modal app logs suno-video-factory-v3-1`
- **Setup Modal**: `modal setup`

### Health Checks
- **Test webhook**: `curl -X POST https://trap--suno-video-factory-v3-3-n8n-webhook.modal.run -H "Content-Type: application/json" -d '{"audio_url": "test", "title": "test", "tags": "test", "video_id": "test"}'`

### Single Test Execution
- **Test video generation**: `modal run modal_video_gen.py` (uses test URLs in main function)

## Code Style Guidelines

### Python (Modal Functions)
- **Imports**: Standard library first, then third-party, one per line
- **Type hints**: Use for all function parameters and return types
- **Docstrings**: Google-style with Args/Returns sections for public functions
- **Naming**: snake_case for variables/functions, PascalCase for classes
- **Error handling**: Try/except with specific exceptions, log errors with context
- **Constants**: UPPER_CASE for module-level constants
- **Line length**: 100 characters max
- **String formatting**: f-strings preferred over .format()

### JavaScript (Tampermonkey Scripts)
- **Variables**: `const` for immutable, `let` for mutable, avoid `var`
- **Functions**: Arrow functions preferred, named functions for exports
- **Async/await**: Use over promises for readability
- **Error handling**: Try/catch with specific error types, console logging
- **Naming**: camelCase for variables/functions, PascalCase for constructors
- **Constants**: UPPER_CASE for configuration objects
- **ES6+ features**: Use modern syntax (destructuring, template literals, etc.)

### General
- **Comments**: Explain why, not what; keep code self-documenting
- **Security**: Never log sensitive data, use environment variables for secrets
- **Performance**: Handle large files efficiently, implement timeouts
- **Logging**: Structured logging with clear prefixes (e.g., "[DOWNLOAD]", "[RENDER]")