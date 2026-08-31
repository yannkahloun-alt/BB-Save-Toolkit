
function showTab(name, button = null, updateHash = true) {
  document.querySelectorAll("[data-tab-panel]").forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.tabPanel === name);
  });

  document.querySelectorAll("[data-tab-button]").forEach((tabButton) => {
    tabButton.classList.toggle("active", tabButton.dataset.tabButton === name);
  });

  if (button) {
    button.classList.add("active");
  }

  if (updateHash && !window.location.hash.startsWith("#bro-")) {
    history.replaceState(null, "", `#${name}`);
  }
}

function filterCategory(category, button) {
  document.querySelectorAll("[data-category]").forEach((element) => {
    const shouldHide =
      category !== "All" && element.dataset.category !== category;

    element.classList.toggle("hidden", shouldHide);
  });

  document.querySelectorAll(".bar button").forEach((element) => {
    element.classList.remove("active");
  });

  button.classList.add("active");
}


function brotherPanels() {
  return Array.from(document.querySelectorAll("details.bro-panel"));
}

function closeOtherBrotherPanels(panel) {
  brotherPanels().forEach((other) => {
    if (other !== panel) {
      other.open = false;
    }
  });
}

function openBrotherPanel(panel, updateHash = true) {
  if (!panel) {
    return;
  }

  closeOtherBrotherPanels(panel);
  panel.open = true;
  ensureFirstRoleOpen(panel);

  if (updateHash) {
    history.replaceState(null, "", `#${panel.id}`);
  }

  requestAnimationFrame(() => {
    panel.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

document.addEventListener("toggle", (event) => {
  const panel = event.target;

  if (
    panel instanceof HTMLDetailsElement &&
    panel.classList.contains("bro-panel")
  ) {
    if (panel.open) {
      closeOtherBrotherPanels(panel);
      ensureFirstRoleOpen(panel);

      requestAnimationFrame(() => {
        panel.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    } else {
      delete panel.dataset.roleInitialized;
    }
  }
}, true);

document.addEventListener("click", (event) => {
  const link = event.target.closest("a.bro-link[href^='#bro-']");

  if (!link) {
    return;
  }

  const targetId = link.getAttribute("href").slice(1);
  const panel = document.getElementById(targetId);

  if (!panel || !panel.classList.contains("bro-panel")) {
    return;
  }

  event.preventDefault();
  showTab("roster", document.querySelector('[data-tab-button="roster"]'), false);
  openBrotherPanel(panel, true);
});


function rolePanels(broPanel) {
  return Array.from(broPanel.querySelectorAll(":scope .roles > details.role-card"));
}

function closeOtherRolePanels(panel) {
  const broPanel = panel.closest("details.bro-panel");
  if (!broPanel) return;
  rolePanels(broPanel).forEach((other) => {
    if (other !== panel) other.open = false;
  });
}

function ensureFirstRoleOpen(broPanel) {
  const panels = rolePanels(broPanel);
  if (!panels.length) {
    return;
  }

  const preferred =
    broPanel.querySelector(":scope .roles > details.role-card.default-open") ||
    panels[0];

  const openPanels = panels.filter((panel) => panel.open);

  // Preserve an explicit user choice while the brother remains open.
  if (openPanels.length === 1 && openPanels[0] === preferred) {
    return;
  }

  // On brother entry, stale/server-rendered state must never override the
  // highest-Fit archetype card chosen by the server-rendered projection order.
  if (!broPanel.dataset.roleInitialized) {
    panels.forEach((panel) => {
      panel.open = panel === preferred;
    });
    broPanel.dataset.roleInitialized = "1";
    return;
  }

  // If the user has collapsed everything, reopening the brother falls back to
  // the highest-Fit card.
  if (!openPanels.length) {
    preferred.open = true;
  }
}

document.addEventListener("toggle", (event) => {
  const panel = event.target;
  if (
    panel instanceof HTMLDetailsElement &&
    panel.classList.contains("role-card") &&
    panel.open
  ) {
    closeOtherRolePanels(panel);
    requestAnimationFrame(() => {
      panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
  }
}, true);


function settlementPanels() {
  return Array.from(document.querySelectorAll("details.settlement-panel"));
}

function closeOtherSettlementPanels(panel) {
  settlementPanels().forEach((other) => {
    if (other !== panel) {
      other.open = false;
    }
  });
}

document.addEventListener("toggle", (event) => {
  const panel = event.target;

  if (
    panel instanceof HTMLDetailsElement &&
    panel.classList.contains("settlement-panel") &&
    panel.open
  ) {
    closeOtherSettlementPanels(panel);

    requestAnimationFrame(() => {
      panel.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }
}, true);


function levelupPanels() {
  return Array.from(document.querySelectorAll("details.levelup-bro-panel"));
}

function closeOtherLevelupPanels(panel) {
  levelupPanels().forEach((other) => {
    if (other !== panel) {
      other.open = false;
    }
  });
}

document.addEventListener("toggle", (event) => {
  const panel = event.target;

  if (
    panel instanceof HTMLDetailsElement &&
    panel.classList.contains("levelup-bro-panel") &&
    panel.open
  ) {
    closeOtherLevelupPanels(panel);

    requestAnimationFrame(() => {
      panel.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }
}, true);


window.addEventListener("DOMContentLoaded", () => {
  const targetId = window.location.hash.slice(1);
  const panel = targetId ? document.getElementById(targetId) : null;

  if (panel && panel.classList.contains("bro-panel")) {
    showTab("roster", document.querySelector('[data-tab-button="roster"]'), false);
    openBrotherPanel(panel, false);
    return;
  }

  brotherPanels().forEach((item) => {
    item.open = false;
  });

  settlementPanels().forEach((item) => {
    item.open = false;
  });

  levelupPanels().forEach((item) => {
    item.open = false;
  });

  if (targetId === "levelup") {
    showTab("levelup", document.querySelector('[data-tab-button="levelup"]'), false);
  } else if (targetId === "management") {
    showTab("management", document.querySelector('[data-tab-button="management"]'), false);
  } else if (targetId === "recruits") {
    showTab("recruits", document.querySelector('[data-tab-button="recruits"]'), false);
  } else {
    showTab("roster", document.querySelector('[data-tab-button="roster"]'), false);
  }
});
