var APP_URL = location.hostname === "localhost" || location.hostname === "127.0.0.1"
  ? "http://localhost:8080"
  : "https://agentception.vercel.app";

document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll("[data-app-link]").forEach(function (link) {
    link.href = APP_URL;
  });

  var header = document.getElementById("site-header");
  var menuButton = document.getElementById("menu-button");
  var mobileNav = document.getElementById("mobile-nav");

  function setMenu(open) {
    menuButton.setAttribute("aria-expanded", String(open));
    menuButton.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
    menuButton.innerHTML = open ? '<i class="ph ph-x"></i>' : '<i class="ph ph-list"></i>';
    mobileNav.hidden = !open;
  }

  menuButton.addEventListener("click", function () {
    setMenu(menuButton.getAttribute("aria-expanded") !== "true");
  });

  mobileNav.querySelectorAll("a").forEach(function (link) {
    link.addEventListener("click", function () { setMenu(false); });
  });

  function updateHeader() {
    header.classList.toggle("scrolled", window.scrollY > 10);
  }
  updateHeader();
  window.addEventListener("scroll", updateHeader, { passive: true });

  var ledgerRows = Array.from(document.querySelectorAll("#hero-ledger .ledger-row"));
  ledgerRows.forEach(function (row, index) {
    window.setTimeout(function () { row.classList.add("is-ready"); }, 180 + (index * 145));
  });

  var reveals = Array.from(document.querySelectorAll(".reveal:not(.is-visible)"));
  if (!("IntersectionObserver" in window)) {
    reveals.forEach(function (item) { item.classList.add("is-visible"); });
    return;
  }

  var revealObserver = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (!entry.isIntersecting) return;
      var siblings = entry.target.parentElement
        ? Array.from(entry.target.parentElement.children).filter(function (child) { return child.classList.contains("reveal"); })
        : [];
      var index = Math.max(0, siblings.indexOf(entry.target));
      window.setTimeout(function () { entry.target.classList.add("is-visible"); }, Math.min(index * 70, 280));
      revealObserver.unobserve(entry.target);
    });
  }, { threshold: 0.14, rootMargin: "0px 0px -48px 0px" });

  reveals.forEach(function (item) { revealObserver.observe(item); });
});
