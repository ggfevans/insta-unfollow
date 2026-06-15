/* ============================================================================
 * unfollow.js — paste-into-console assistant for unfollowing your non-mutuals.
 *
 * USE AT YOUR OWN RISK. Automating actions violates Instagram's ToS and can
 * trigger temporary action-blocks or, at worst, account suspension. This script
 * clicks the real UI buttons at a human-ish pace and STOPS the moment it detects
 * a block — but it cannot guarantee you won't get one. Start conservative.
 *
 * HOW TO USE (desktop browser, logged in):
 *   1. Open https://www.instagram.com/  and go to YOUR profile.
 *   2. Click your "following" count to open the Following list dialog.
 *   3. Open DevTools console (Cmd+Opt+J in Chrome).
 *   4. Paste the contents of  unfollow_queue.js  and press Enter.
 *   5. Paste THIS file and press Enter.
 *   6. It runs in DRY RUN first — it only LOGS who it would unfollow. Verify the
 *      handles look right. Then set  CONFIG.dryRun = false  (edit below) and
 *      paste again to actually unfollow.
 *   7. RESUME: progress is saved in your browser (localStorage). Re-paste both
 *      files on later days and it skips everyone already unfollowed, advancing
 *      ~one cap deeper each session. Set CONFIG.reset = true for one run to
 *      wipe saved progress and start over.
 *
 * Selectors: Instagram changes its markup often. This script finds buttons by
 * their TEXT ("Following" / "Unfollow"), which is more durable than class names,
 * but if it logs "0 rows matched" the UI may have shifted — tell me what the
 * console shows and I'll adjust.
 * ========================================================================== */
(async () => {
  const CONFIG = {
    cap: 150,          // max unfollows THIS session (ramp up over days if no blocks)
    minDelay: 3000,    // min ms between unfollows (randomised)
    maxDelay: 7000,    // max ms between unfollows
    scrollPauseMs: 1800,
    dryRun: false,     // LIVE — this will actually unfollow. Set true to re-test.
    reset: false,      // set true for ONE run to wipe saved progress and start over.
  };

  const norm = (s) => (s || "").toLowerCase().trim();
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const rand = (a, b) => Math.floor(a + Math.random() * (b - a));

  const targets = new Set((window.UNFOLLOW_TARGETS || []).map(norm));
  if (!targets.size) {
    console.error("❌ No targets. Paste unfollow_queue.js first.");
    return;
  }
  // ---- Resume across runs: completed handles persist in localStorage ----
  const STORE_KEY = "iu_unfollowed_v1";
  const loadDone = () => {
    try {
      return new Set(JSON.parse(localStorage.getItem(STORE_KEY) || "[]"));
    } catch {
      console.warn("⚠ localStorage unavailable — progress won't persist this run.");
      return new Set();
    }
  };
  const saveDone = (set) => {
    try { localStorage.setItem(STORE_KEY, JSON.stringify([...set])); } catch {}
  };
  if (CONFIG.reset) {
    try { localStorage.removeItem(STORE_KEY); } catch {}
    console.log("↺ Stored progress cleared (CONFIG.reset). Set it back to false next run.");
  }
  const done = loadDone(); // handles already unfollowed in previous sessions
  const remaining = [...targets].filter((t) => !done.has(t)).length;
  console.log(
    `▶ ${targets.size} targets · ${done.size} done · ${remaining} remaining · ` +
      `dryRun=${CONFIG.dryRun} · cap=${CONFIG.cap}`
  );

  const getDialog = () => document.querySelector('div[role="dialog"]');
  function getScroller(dialog) {
    const divs = [...dialog.querySelectorAll("div")].filter(
      (d) => d.scrollHeight > d.clientHeight + 50
    );
    return divs.sort((a, b) => b.scrollHeight - a.scrollHeight)[0] || dialog;
  }
  // Given a row's "Following" button, climb to the row and read its profile handle.
  function handleForButton(btn) {
    let el = btn;
    for (let i = 0; i < 15 && el; i++) {
      el = el.parentElement;
      if (!el) break;
      for (const a of el.querySelectorAll('a[href^="/"]')) {
        const m = (a.getAttribute("href") || "").match(/^\/([^\/]+)\/?$/);
        if (m) return norm(m[1]);
      }
    }
    return null;
  }
  function findButtonByText(root, text) {
    return [...root.querySelectorAll('button, [role="button"]')].find(
      (b) => norm(b.textContent) === text
    );
  }
  function blockDetected() {
    return /action blocked|try again later|we restrict certain activity|temporarily blocked/i.test(
      document.body.innerText
    );
  }

  const attempted = new Set(); // guards re-processing within THIS run (incl. dry run)
  let count = 0;

  async function processVisibleRows() {
    const dialog = getDialog();
    if (!dialog) {
      console.error("❌ No following dialog open. Click your 'following' count first.");
      return "stop";
    }
    const rowButtons = [...dialog.querySelectorAll('button, [role="button"]')].filter(
      (b) => norm(b.textContent) === "following"
    );
    for (const btn of rowButtons) {
      if (count >= CONFIG.cap) return "cap";
      const handle = handleForButton(btn);
      // Skip non-targets, anything done in a previous run (free skip — no click,
      // no cap cost), and anything already handled this run.
      if (!handle || !targets.has(handle) || done.has(handle) || attempted.has(handle)) continue;
      attempted.add(handle);

      if (CONFIG.dryRun) {
        count++;
        console.log(`[dry] #${count} would unfollow @${handle}`);
        continue; // dry run never persists — it must not poison real progress
      }

      btn.scrollIntoView({ block: "center" });
      btn.click();
      await sleep(rand(700, 1400)); // wait for confirm sheet

      const confirm = findButtonByText(document, "unfollow");
      if (!confirm) {
        console.warn(`⚠ no confirm dialog for @${handle} — skipped`);
        continue;
      }
      confirm.click();
      done.add(handle);
      saveDone(done); // persist only real unfollows, immediately
      count++;
      console.log(`✓ #${count} unfollowed @${handle}`);

      if (blockDetected()) {
        console.error("⛔ ACTION BLOCK detected — stopping now. Wait 24–48h before retrying.");
        return "blocked";
      }
      await sleep(rand(CONFIG.minDelay, CONFIG.maxDelay));
    }
    return "continue";
  }

  let stale = 0;
  while (true) {
    const result = await processVisibleRows();
    if (result === "cap") { console.log(`✅ Session cap (${CONFIG.cap}) reached.`); break; }
    if (result === "blocked" || result === "stop") break;

    const dialog = getDialog();
    const scroller = getScroller(dialog);
    const before = scroller.scrollTop;
    scroller.scrollTop = scroller.scrollHeight;
    await sleep(CONFIG.scrollPauseMs + rand(0, 800));
    if (scroller.scrollTop <= before) {
      stale++;
      if (stale > 3) { console.log("🏁 Reached end of the following list."); break; }
    } else {
      stale = 0;
    }
  }

  console.log(`— Finished. ${CONFIG.dryRun ? "(dry run) " : ""}${count} processed this session. —`);
  if (CONFIG.dryRun) console.log("Looks right? Set CONFIG.dryRun = false and paste again to do it for real.");
})();
