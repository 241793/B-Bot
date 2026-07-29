(() => {
  "use strict";

  const FALLBACK = {
    name: "B-BOT",
    version: "1.1.2",
    title: "AI 驱动的智能机器人框架",
    description:
      "多渠道接入、独立 Agent、插件扩展、AI 工作流与内置青龙，在一套 Web 管理台中协同运行。",
    dockerSocketNotice:
      "命令中的 docker.sock 挂载用于容器管理，会授予 B-BOT 容器访问宿主 Docker 守护进程的能力。仅在受控主机上部署。",
    github: "https://github.com/241793/B-Bot",
    docsUrl: "https://github.com/241793/B-Bot/blob/main/README.md",
    blog: "https://bchome.dpdns.org",
    dockerImage: "241793/b-bot:latest",
    androidApp:
      "https://github.com/241793/B-Bot/releases/download/1.0.9/b-bot1.0.4.apk",
    dockerRun:
      "docker run -d \\\n  --name bbot \\\n  --restart unless-stopped \\\n  -p 5000:5000 \\\n  -p 8888:8888 \\\n  -v /var/run/docker.sock:/var/run/docker.sock \\\n  -v /your/data/path:/app/mount \\\n  241793/b-bot:latest",
  };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const reducedMotionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");

  function safeHttpUrl(value) {
    try {
      const url = new URL(String(value));
      return url.protocol === "http:" || url.protocol === "https:" ? url.href : null;
    } catch {
      return null;
    }
  }

  function setText(binding, value) {
    if (value == null) return;
    $$(`[data-bind='${binding}']`).forEach((el) => {
      if (el.tagName !== "A") el.textContent = String(value);
    });
  }

  function applyConfig(config) {
    const data = { ...FALLBACK, ...config };

    setText("name", data.name);
    setText("version", data.version);
    setText("version-label", data.version);
    setText("description", data.description);
    setText("dockerImage", data.dockerImage);
    setText("dockerSocketNotice", data.dockerSocketNotice);

    const links = {
      github: data.github,
      docsUrl: data.docsUrl,
      blog: data.blog,
      androidApp: data.androidApp,
    };

    Object.entries(links).forEach(([binding, value]) => {
      const url = safeHttpUrl(value);
      if (!url) return;
      $$(`[data-bind='${binding}']`).forEach((el) => {
        if (el.tagName === "A") el.href = url;
      });
    });

    const command = $("#docker-cmd code") || $("#docker-cmd");
    if (command && data.dockerRun) {
      command.textContent = String(data.dockerRun).replace(/\\n/g, "\n");
    }

    document.title = `${data.name} — ${data.title}`;
    const description = $("meta[name='description']");
    if (description) description.content = data.description;
  }

  async function loadConfig() {
    try {
      const response = await fetch("./config.json", { cache: "no-store" });
      if (!response.ok) throw new Error(String(response.status));
      applyConfig(await response.json());
    } catch {
      applyConfig(FALLBACK);
    }
  }

  function setupNav() {
    const nav = $("#nav");
    const links = $("#nav-links");
    const button = $("#menu-btn");
    if (!nav || !links || !button) return;

    button.hidden = false;

    const setMenuState = (open, restoreFocus = false) => {
      links.classList.toggle("is-open", open);
      button.setAttribute("aria-expanded", String(open));
      button.setAttribute("aria-label", open ? "关闭菜单" : "打开菜单");
      if (restoreFocus) button.focus();
    };

    const updateNav = () => {
      nav.classList.toggle("is-scrolled", window.scrollY > 8);
    };

    updateNav();
    window.addEventListener("scroll", updateNav, { passive: true });

    button.addEventListener("click", () => {
      setMenuState(button.getAttribute("aria-expanded") !== "true");
    });

    links.addEventListener("click", (event) => {
      if (event.target.closest("a")) setMenuState(false);
    });

    document.addEventListener("pointerdown", (event) => {
      if (button.getAttribute("aria-expanded") !== "true") return;
      if (!nav.contains(event.target)) setMenuState(false);
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && button.getAttribute("aria-expanded") === "true") {
        setMenuState(false, true);
      }
    });

    window.addEventListener("resize", () => {
      if (window.innerWidth > 734) setMenuState(false);
    });
  }

  function setupReveal() {
    if (reducedMotionQuery.matches || !("IntersectionObserver" in window)) return;

    const nodes = $$(".reveal");
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-in");
          observer.unobserve(entry.target);
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -7% 0px" }
    );

    nodes.forEach((node) => {
      const rect = node.getBoundingClientRect();
      if (rect.top > window.innerHeight * 0.88) {
        node.classList.add("is-pending");
        observer.observe(node);
      }
    });
  }

  function setupCopy() {
    const button = $("#copy-btn");
    const command = $("#docker-cmd");
    const status = $("#copy-status");
    if (!button || !command) return;

    button.hidden = false;
    let restoreTimer = 0;

    const copyFallback = (text) => {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.readOnly = true;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      const copied = document.execCommand("copy");
      textarea.remove();
      if (!copied) throw new Error("copy failed");
    };

    const report = (message, success) => {
      window.clearTimeout(restoreTimer);
      button.textContent = message;
      button.classList.toggle("is-copied", success);
      if (status) status.textContent = success ? "Docker 命令已复制到剪贴板" : "复制失败，请手动选择命令";
      restoreTimer = window.setTimeout(() => {
        button.textContent = "复制";
        button.classList.remove("is-copied");
        if (status) status.textContent = "";
      }, 1600);
    };

    button.addEventListener("click", async () => {
      const text = (command.innerText || command.textContent || "").trim();
      try {
        if (navigator.clipboard?.writeText) {
          await navigator.clipboard.writeText(text);
        } else {
          copyFallback(text);
        }
        report("已复制", true);
      } catch {
        report("复制失败", false);
      }
    });
  }

  function setupScenes() {
    const switcher = $("[data-scene-switcher]");
    if (!switcher) return;

    const tabs = $$("[role='tab']", switcher);
    const panels = $$("[role='tabpanel']", switcher);
    if (!tabs.length || tabs.length !== panels.length) return;

    const tabList = $("[role='tablist']", switcher);
    if (tabList) tabList.hidden = false;

    const activate = (index, moveFocus = false) => {
      tabs.forEach((tab, tabIndex) => {
        const active = tabIndex === index;
        tab.setAttribute("aria-selected", String(active));
        tab.tabIndex = active ? 0 : -1;
      });

      panels.forEach((panel, panelIndex) => {
        const active = panelIndex === index;
        panel.hidden = !active;
        panel.classList.remove("scene-enter");
        if (active && !reducedMotionQuery.matches) {
          void panel.offsetWidth;
          panel.classList.add("scene-enter");
        }
      });

      if (moveFocus) {
        tabs[index].focus();
        tabs[index].scrollIntoView({
          behavior: reducedMotionQuery.matches ? "auto" : "smooth",
          block: "nearest",
          inline: "nearest",
        });
      }
    };

    const hashIndex = panels.findIndex((panel) => `#${panel.id}` === window.location.hash);
    activate(hashIndex >= 0 ? hashIndex : 0);

    tabs.forEach((tab, index) => {
      tab.addEventListener("click", () => activate(index));
      tab.addEventListener("keydown", (event) => {
        let next = index;
        if (event.key === "ArrowRight" || event.key === "ArrowDown") next = (index + 1) % tabs.length;
        else if (event.key === "ArrowLeft" || event.key === "ArrowUp") next = (index - 1 + tabs.length) % tabs.length;
        else if (event.key === "Home") next = 0;
        else if (event.key === "End") next = tabs.length - 1;
        else return;
        event.preventDefault();
        activate(next, true);
      });
    });
  }

  function setupYear() {
    const year = $("#year");
    if (year) year.textContent = String(new Date().getFullYear());
  }

  function boot() {
    document.documentElement.classList.add("js");
    setupYear();
    setupNav();
    setupReveal();
    setupCopy();
    setupScenes();
    loadConfig();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
