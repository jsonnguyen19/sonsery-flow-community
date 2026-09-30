window.__RUNCTX__ = window.__RUNCTX__ || {};

function setNativeTextareaValue(textarea, text) {
  const prototype = Object.getPrototypeOf(textarea);
  const descriptor = Object.getOwnPropertyDescriptor(prototype, "value");

  if (descriptor?.set) {
    descriptor.set.call(textarea, text);
  } else {
    textarea.value = text;
  }
}

function dispatchComposerEvents(target, text) {
  const events = [
    new InputEvent("beforeinput", {
      bubbles: true,
      cancelable: true,
      inputType: "insertText",
      data: text,
    }),
    new InputEvent("input", {
      bubbles: true,
      inputType: "insertText",
      data: text,
    }),
    new Event("change", { bubbles: true }),
    new KeyboardEvent("keyup", { bubbles: true, key: " ", code: "Space" }),
  ];

  events.forEach((event) => target.dispatchEvent(event));
}

function focusTarget(target) {
  target.scrollIntoView?.({ block: "center", inline: "nearest" });
  target.focus?.({ preventScroll: true });
}

function setTextareaText(target, text) {
  focusTarget(target);
  // Clear existing value first
  setNativeTextareaValue(target, "");
  setNativeTextareaValue(target, text);
  dispatchComposerEvents(target, text);
  return target.value === text;
}

function setContentEditableText(target, text) {
  focusTarget(target);

  // Clear existing content first to prevent file attachment conversion
  target.textContent = "";

  // Insert as plain text node
  const textNode = document.createTextNode(text);
  target.appendChild(textNode);

  dispatchComposerEvents(target, text);

  const currentText = target.innerText || target.textContent || "";
  return currentText === text;
}

window.__RUNCTX__.DomTransport = {
  inject(text) {
    const target = window.__RUNCTX__.AdapterRegistry.getChatInput();
    if (!target) return false;

    if (target.tagName === "TEXTAREA") {
      return setTextareaText(target, text);
    }

    if (target.isContentEditable || target.getAttribute("contenteditable") === "true") {
      return setContentEditableText(target, text);
    }

    return false;
  },
};
