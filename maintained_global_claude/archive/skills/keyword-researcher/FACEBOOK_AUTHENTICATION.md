# Facebook Extractor - Authentication Requirement

## Summary
The Facebook feed reader cannot extract search results or feed data without user authentication. Facebook requires users to be logged in before accessing search results or personalized content.

## Testing Results

### Test Command
```bash
uv run src/feed_reader.py facebook "technology"
```

### Debug Output
When running the Facebook extractor without authentication, you will see:

```
[DEBUG] Page content length: 86611 characters
[DEBUG] Page title: Page Not Found
[DEBUG] Page URL: https://www.facebook.com/search/top/?q=technology
[DEBUG] Found 0 article elements with role='article'
[DEBUG] Page appears to require authentication (login/authenticate text found)
```

### Error Message
The extractor returns a helpful error message:

```
ERROR: Facebook Search Requires Authentication

Facebook's search results page requires you to be logged in. This tool cannot 
extract Facebook search results without valid credentials.

Why authentication is needed:
- Facebook restricts search functionality to authenticated users
- Search results are personalized to your account
- The page content is not available to unauthenticated requests

To extract Facebook content, you would need to:
1. Implement Facebook OAuth2 authentication
2. Use Facebook Graph API (requires API access approval)
3. Store and manage session credentials securely

Alternative: Use the Facebook Graph API or official SDKs for programmatic access.
```

## Technical Details

### Page Structure
When unauthenticated:
- Facebook redirects to a login/authentication page
- The HTML contains "Page Not Found" in the title
- The page structure does not contain `role='article'` elements
- The page contains login/authentication indicators in the HTML

### Detection Mechanism
The extractor detects authentication requirements by:
1. Looking for `role='article'` elements (only present in authenticated feeds)
2. Checking for "login" or "authenticate" text in the page content
3. Providing a clear, actionable error message when authentication is required

### Limitations

**Cannot extract without authentication because:**
- Facebook blocks unauthenticated requests to search results pages
- The page structure is completely different for logged-out users
- Facebook's terms of service restrict scraping
- Playwright cannot automate Facebook login due to:
  - Anti-automation detection (reCAPTCHA, etc.)
  - Browser fingerprinting evasion challenges
  - Rate limiting and request throttling
  - Complex JavaScript rendering and state management

## Solutions

### Option 1: Facebook Graph API (Recommended)
```
- Requires API approval and credentials
- Official, supported method
- Requires OAuth2 implementation
- Limited to approved use cases
```

### Option 2: Manual Authentication
```
- Log in to Facebook in a browser before scraping
- Save session cookies
- Reuse authenticated session in Playwright
- Still subject to terms of service restrictions
```

### Option 3: Use Official Tools
```
- Facebook Business SDK
- Meta for Developers tools
- Official APIs with proper authentication
```

## Code Implementation

The Facebook extractor (`src/extractors/facebook.py`):

1. **Detection**: Checks page content for authentication indicators
2. **Error Handling**: Returns clear error message instead of empty results
3. **Debug Logging**: Provides page title, URL, and element count for debugging
4. **Extraction Logic**: Implements post parsing logic for when authenticated content IS available

## Testing with Authenticated Content

To test the extraction logic with authenticated content:

1. Use the `test_facebook_selectors.py` script which tests selectors against sample HTML
2. Save authenticated Facebook HTML to a file
3. Modify the extractor temporarily to read from that file for testing

```bash
uv run tests/test_facebook_selectors.py
```

## Summary

The Facebook extractor correctly:
- ✓ Detects when authentication is required
- ✓ Provides helpful error messages
- ✓ Logs debug information for troubleshooting
- ✓ Documents the authentication limitation
- ✗ Cannot extract unauthenticated content (expected behavior)

**Status**: WORKING AS DESIGNED - The extractor correctly identifies and reports the authentication requirement with helpful guidance.
