(() => {
  const norm = (s) => (s || "").toLowerCase().trim();
  const targets = new Set((window.UNFOLLOW_TARGETS || []).map(norm));
  const dialog = document.querySelector('div[role="dialog"]');
  console.log("dialog found:", !!dialog);
  if (!dialog) {
    console.log("No dialog — is the Following list open as a full page instead of a popup?");
    return;
  }
  const anchors = [...dialog.querySelectorAll('a[href^="/"]')];
  console.log("anchors found:", anchors.length);
  console.log("sample hrefs:", anchors.slice(0, 8).map((a) => a.getAttribute("href")));
  const handles = anchors
    .map((a) => {
      const m = (a.getAttribute("href") || "").match(/^\/([^\/]+)\/?$/);
      return m ? norm(m[1]) : null;
    })
    .filter(Boolean);
  console.log("parsed handles:", handles.slice(0, 8));
  const hit = handles.filter((h) => targets.has(h));
  console.log("handles matching your target list:", hit.length, hit.slice(0, 8));
  const btns = [...dialog.querySelectorAll('button, [role="button"]')];
  console.log("buttons in dialog:", btns.length);
  console.log("distinct button labels:", [
    ...new Set(btns.map((b) => norm(b.textContent)).filter(Boolean)),
  ]);
})();
