/**
 * Explain a term in place: `.hm-hint` buttons open their `.hm-hint__bubble`
 * popover (humemai/design-system #12; mirrored from Stateloop's hint.js).
 *
 *   <button type="button" class="hm-hint" popovertarget="hint-x" popovertargetaction="show"
 *           aria-label="What is X?" aria-describedby="hint-x">?</button>
 *   <span id="hint-x" class="hm-hint__bubble" popover role="tooltip">One sentence.</span>
 *
 * The browser's Popover API does the opening and the dismissing: a click, tap
 * or Enter shows it, and a tap outside or Esc closes it. This adds what it
 * lacks: placing the bubble by its button and keeping it on screen, following
 * it while the page or a panel scrolls, and hover with a mouse (it opens on
 * enter and closes on leave, unless it was clicked, which pins it). The
 * listeners sit on the document, so hints rendered later -- by an app that
 * re-renders with innerHTML -- work with no per-render wiring. Call it once.
 *
 * @param {Document} [doc]
 * @returns {() => void} cleanup
 */
const GAP = 6;
const EDGE = 8;
let bound = null;

export function bindHints(doc = document) {
  if (bound) return bound;
  const win = doc.defaultView;
  let open = null;

  const bubbleOf = (trigger) => doc.getElementById(trigger.getAttribute("popovertarget") || "");
  const triggerOf = (bubble) =>
    Array.from(doc.querySelectorAll(".hm-hint")).find((t) => t.getAttribute("popovertarget") === bubble.id);
  const hintAt = (target) => (target && target.closest ? target.closest(".hm-hint") : null);
  const isBubble = (el) => el && el.classList && el.classList.contains("hm-hint__bubble");
  const isOpen = (bubble) => bubble.matches(":popover-open");

  function place(bubble) {
    const trigger = triggerOf(bubble);
    if (!trigger) return;
    const t = trigger.getBoundingClientRect();
    const b = bubble.getBoundingClientRect();
    const vw = doc.documentElement.clientWidth;
    const vh = win.innerHeight;
    const left = Math.max(EDGE, Math.min(t.left + t.width / 2 - b.width / 2, vw - b.width - EDGE));
    let top = t.bottom + GAP;
    if (top + b.height > vh - EDGE && t.top - GAP - b.height >= EDGE) top = t.top - GAP - b.height;
    bubble.style.left = `${Math.round(left)}px`;
    bubble.style.top = `${Math.round(top)}px`;
    bubble.dataset.placed = "";
  }

  // `toggle` does not bubble, but a capturing listener on the document sees it.
  function onToggle(e) {
    const bubble = e.target;
    if (!isBubble(bubble)) return;
    const trigger = triggerOf(bubble);
    if (e.newState === "open") {
      open = bubble;
      place(bubble);
      if (trigger) trigger.setAttribute("aria-expanded", "true");
    } else {
      if (open === bubble) open = null;
      delete bubble.dataset.placed;
      delete bubble.dataset.pinned;
      if (trigger) trigger.setAttribute("aria-expanded", "false");
    }
  }

  // A click pins it: leaving with the mouse no longer closes it.
  function onClick(e) {
    const trigger = hintAt(e.target);
    const bubble = trigger && bubbleOf(trigger);
    if (bubble) bubble.dataset.pinned = "";
  }

  // Hover is for a mouse only: a touch screen has no hover, and its tap is the click.
  function onOver(e) {
    if (e.pointerType !== "mouse") return;
    const trigger = hintAt(e.target);
    const bubble = trigger && bubbleOf(trigger);
    if (bubble && !isOpen(bubble)) bubble.showPopover();
  }

  function onOut(e) {
    if (e.pointerType !== "mouse") return;
    const trigger = hintAt(e.target);
    if (!trigger || trigger.contains(e.relatedTarget)) return;
    const bubble = bubbleOf(trigger);
    if (bubble && isOpen(bubble) && !("pinned" in bubble.dataset)) bubble.hidePopover();
  }

  function follow() {
    if (open) place(open);
  }

  doc.addEventListener("toggle", onToggle, true);
  doc.addEventListener("click", onClick, true);
  doc.addEventListener("pointerover", onOver, true);
  doc.addEventListener("pointerout", onOut, true);
  win.addEventListener("scroll", follow, true);
  win.addEventListener("resize", follow);

  bound = () => {
    doc.removeEventListener("toggle", onToggle, true);
    doc.removeEventListener("click", onClick, true);
    doc.removeEventListener("pointerover", onOver, true);
    doc.removeEventListener("pointerout", onOut, true);
    win.removeEventListener("scroll", follow, true);
    win.removeEventListener("resize", follow);
    bound = null;
  };
  return bound;
}

/**
 * The "?" and its bubble for a glossary term, so no app keeps a private copy.
 *
 *   const GLOSSARY = { fit: { term: "the fit score", text: "How well they match, 1 to 5.", learnMore: "https://example.com/fit" } };
 *   header.innerHTML = `Fit ${termHint(GLOSSARY, "fit", "the fit score")}`;          // an app that renders with innerHTML
 *   header.append("Fit ", termHintElement(GLOSSARY, "fit", "the fit score"));         // an app with an h() helper
 *
 * Both give the markup in the header of this file: `button.hm-hint` (`aria-label` "What is <term>?") and `span.hm-hint__bubble`,
 * with a fresh id (`hm-hint-1`, `hm-hint-2`, ...) from one counter in this module. A key the glossary lacks throws an Error that
 * names it: a silent empty string hides a typo and drops the explanation. `learnMore` (an http(s) or site-relative URL) adds a last
 * "Learn more" line to the bubble. `term` defaults to the entry's own `term`.
 */
let hintSeq = 0;

function entryFor(glossary, key) {
  const entry = glossary && Object.prototype.hasOwnProperty.call(glossary, key) ? glossary[key] : undefined;
  if (!entry || typeof entry.text !== "string" || !entry.text) {
    throw new Error(`termHint: no glossary entry for key "${key}"`);
  }
  if (entry.learnMore != null && !/^(https?:\/\/|\/(?!\/))/.test(entry.learnMore)) {
    throw new Error(`termHint: learnMore of "${key}" must be an http(s) or site-relative URL`);
  }
  return entry;
}

function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

const MORE = "Learn more";

export function termHint(glossary, key, term) {
  const entry = entryFor(glossary, key);
  const id = `hm-hint-${++hintSeq}`;
  const label = esc(`What is ${term ?? entry.term ?? key}?`);
  const more = entry.learnMore ? `<br><a href="${esc(entry.learnMore)}" target="_blank" rel="noopener">${MORE}</a>` : "";
  return `<button type="button" class="hm-hint" popovertarget="${id}" popovertargetaction="show" aria-label="${label}" aria-describedby="${id}">?</button>`
    + `<span id="${id}" class="hm-hint__bubble" popover role="tooltip">${esc(entry.text)}${more}</span>`;
}

export function termHintElement(glossary, key, term, doc = globalThis.document) {
  const entry = entryFor(glossary, key);
  const id = `hm-hint-${++hintSeq}`;
  const button = doc.createElement("button");
  button.type = "button";
  button.className = "hm-hint";
  button.setAttribute("popovertarget", id);
  button.setAttribute("popovertargetaction", "show");
  button.setAttribute("aria-label", `What is ${term ?? entry.term ?? key}?`);
  button.setAttribute("aria-describedby", id);
  button.textContent = "?";
  const bubble = doc.createElement("span");
  bubble.id = id;
  bubble.className = "hm-hint__bubble";
  bubble.setAttribute("popover", "");
  bubble.setAttribute("role", "tooltip");
  bubble.append(entry.text);
  if (entry.learnMore) {
    const a = doc.createElement("a");
    a.href = entry.learnMore;
    a.target = "_blank";
    a.rel = "noopener";
    a.textContent = MORE;
    bubble.append(doc.createElement("br"), a);
  }
  const frag = doc.createDocumentFragment();
  frag.append(button, bubble);
  return frag;
}
