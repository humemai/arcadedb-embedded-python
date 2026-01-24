window.MathJax = {
  tex: {
    inlineMath: [['\\(', '\\)'], ['$', '$']]
  },
  options: {
    ignoreHtmlClass: '.*',
    processHtmlClass: 'arithmatex'
  }
};

document$.subscribe(() => {
  if (window.MathJax && window.MathJax.typesetPromise) {
    window.MathJax.typesetPromise();
  }
});
