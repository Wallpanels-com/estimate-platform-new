# Clipboard photos (shared release)

The Pre/Final zone photo panel accepts a native paste into a labeled field next
to the existing upload action. Ctrl+V on Windows/Linux or Command+V on macOS uses
the browser's paste event; no clipboard-read permission or external image URL
fetch is needed. Text fields elsewhere retain their normal paste behavior.

Only one actual image file is accepted per paste. JPEG, PNG and WebP use the
same validation as the file picker (20 MB, four slots maximum). The first empty
slot is selected; a full zone offers no paste field. A synchronous request lock
prevents duplicate rapid pastes, and controls stay disabled while saving.

Both paths call Builder's existing revision-aware multipart POST. The existing
backend validates the image, writes its bytes to persistent storage, inserts its
database record and commits before acknowledging. Reload and reopening fetch
that stored image. The UI confirms successful saving; while uploading, it asks
the user to keep the tab open. Builder's existing beforeunload warning protects
unfinished uploads; closing a tab before a save completes cannot guarantee it.

Verification: catalogue UI regression covers regular uploads/replacement, native
paste event handling, wrong/multiple/text clipboard contents, duplicate requests,
full slots and failed-save status. test_photo_persistence checks actual PNG bytes
and committed records in fresh database sessions for Pre and Final. Headless
Chromium QA uses an actual clipboard image and Command+V with isolated API
fixtures, then reloads/reopens the tab and waits for image decoding. Responsive
screenshots at 1440, 1280, 1024, 768 and 390 px were inspected. No real customer
estimate was modified by QA. No feature flag or owner-only restriction applies.
