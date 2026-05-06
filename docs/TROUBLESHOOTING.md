# Troubleshooting Guide

## Common Errors

### "Expecting value: line 1 column 1 (char 0)"

This error occurs when the ChatGPT API returns an invalid response.

**Causes:**
1. **Missing proxy configuration** - If you're behind a proxy, set `BROWSER_PROXY` in `.env`
2. **Cloudflare challenge** - ChatGPT detected automated access
3. **Expired session token** - Get a fresh token from your browser

**Solutions:**
1. Configure proxy in `.env`:
   ```
   BROWSER_PROXY=http://127.0.0.1:7890
   ```
2. Login via browser first, then try again
3. Clear browser profile: `rm -rf ./browser_profile`

### Cloudflare Challenge Detected

**Symptoms:**
- Error message mentions "Cloudflare" or "challenge"
- Browser shows "Just a moment..." page

**Solutions:**
1. Open ChatGPT in your regular browser
2. Complete any CAPTCHA challenges
3. Wait a few minutes before retrying
4. Consider using a residential proxy

### Connection Timeout

**Symptoms:**
- Error: "Request timed out"
- Login takes too long

**Solutions:**
1. Check your network connectivity
2. Verify proxy is running (if configured)
3. Increase timeout: `gpt-proxy login --timeout 600`

### Proxy Connection Issues

**Symptoms:**
- Error: "Connection refused"
- Error: "Proxy connection failed"

**Solutions:**
1. Verify proxy URL format: `http://host:port`
2. Check if proxy server is running
3. Test proxy with curl: `curl -x http://proxy:port https://chat.openai.com`

### Session Token Invalid

**Symptoms:**
- Error: "Invalid session token"
- Error: "Token expired"

**Solutions:**
1. Get a fresh session token from browser
2. Clear browser profile and re-login
3. Check if you can access chat.openai.com normally

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# Proxy settings (required if behind firewall)
BROWSER_PROXY=http://127.0.0.1:7890

# HTTP client settings
HTTP_TIMEOUT=30.0
HTTP_CONNECT_TIMEOUT=10.0

# Browser profile directory
BROWSER_PROFILE_DIR=./browser_profile
```

### Debug Mode

Enable debug logging:

```env
LOG_LEVEL=DEBUG
APP_DEBUG=true
```

## Getting Help

1. Check server logs for detailed error messages
2. Try the manual token method: `gpt-proxy help-token`
3. Open an issue: https://github.com/art3m1s-tju/GPT_reverse/issues
