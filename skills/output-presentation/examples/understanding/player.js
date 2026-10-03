(() => {
  const tabs = [...document.querySelectorAll('.format-tabs [role="tab"]')];
  const modes = tabs.map(tab => tab.dataset.mode);
  const panels = modes.map(mode => document.getElementById(mode));

  function select(mode, focus = false, updateHash = true) {
    if (!modes.includes(mode)) return;
    tabs.forEach(tab => {
      const selected = tab.dataset.mode === mode;
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
      if (selected && focus) tab.focus();
    });
    panels.forEach(panel => {
      panel.hidden = panel.id !== mode;
      if (panel.hidden) panel.querySelector('video')?.pause();
    });
    if (mode === 'interactive') {
      const frame = document.querySelector('#interactive iframe');
      if (!frame.hasAttribute('src')) frame.src = frame.dataset.src;
    }
    if (updateHash) history.replaceState(null, '', '#' + mode);
  }

  document.querySelectorAll('[data-mode]').forEach(control => {
    control.addEventListener('click', event => {
      event.preventDefault();
      select(control.dataset.mode);
      if (control.matches('a')) {
        document.getElementById('experience').scrollIntoView({
          behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'
        });
      }
    });
  });
  tabs.forEach((tab, index) => {
    tab.addEventListener('keydown', event => {
      let target;
      if (event.key === 'ArrowRight') target = (index + 1) % tabs.length;
      if (event.key === 'ArrowLeft') target = (index + tabs.length - 1) % tabs.length;
      if (event.key === 'Home') target = 0;
      if (event.key === 'End') target = tabs.length - 1;
      if (target === undefined) return;
      event.preventDefault();
      select(modes[target], true);
    });
  });
  addEventListener('hashchange', () => select(location.hash.slice(1), false, false));
  select(location.hash.slice(1), false, false);
})();
