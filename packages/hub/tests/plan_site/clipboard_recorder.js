window.copiedTexts = [];
Object.defineProperty(navigator, "clipboard", {
  value: {
    writeText: function (text) {
      window.copiedTexts.push(text);
      return Promise.resolve();
    }
  }
});
