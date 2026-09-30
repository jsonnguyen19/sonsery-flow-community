// ============================================================
// CONTENT SCRIPT MARKER — must run FIRST
// ============================================================
// Declares that all modules loaded after this file run inside a content
// script (as opposed to the popup). Shared modules can check this marker to
// distinguish the two contexts.
//
// This file MUST be the first entry in manifest.json content_scripts[0].js
// so the marker is set before any module that might call
// AdapterRegistry.getCurrentAdapter() runs.

window.__RUNCTX_IS_CONTENT_SCRIPT__ = true;
