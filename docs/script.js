(() => {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  // ----- Particles (light) -----
  class Particles {
    constructor(canvas) {
      this.canvas = canvas;
      this.ctx = canvas.getContext("2d");
      this.dots = [];
      this.max = 56;
      this.resize();
      this.spawn();
      this.loop = this.loop.bind(this);
      requestAnimationFrame(this.loop);
      window.addEventListener("resize", () => this.resize());
    }
    resize() {
      this.canvas.width = window.innerWidth;
      this.canvas.height = window.innerHeight;
    }
    spawn() {
      this.dots = Array.from({ length: this.max }, () => ({
        x: Math.random() * this.canvas.width,
        y: Math.random() * this.canvas.height,
        vx: (Math.random() - 0.5) * 0.35,
        vy: (Math.random() - 0.5) * 0.35,
        r: Math.random() * 1.6 + 0.6,
        a: Math.random() * 0.35 + 0.15,
      }));
    }
    loop() {
      const { ctx, canvas, dots } = this;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (let i = 0; i < dots.length; i++) {
        const p = dots[i];
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0) p.x = canvas.width;
        if (p.x > canvas.width) p.x = 0;
        if (p.y < 0) p.y = canvas.height;
        if (p.y > canvas.height) p.y = 0;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(34, 211, 238, ${p.a})`;
        ctx.fill();
        for (let j = i + 1; j < dots.length; j++) {
          const q = dots[j];
          const dx = p.x - q.x;
          const dy = p.y - q.y;
          const d = Math.hypot(dx, dy);
          if (d < 120) {
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(q.x, q.y);
            ctx.strokeStyle = `rgba(129, 140, 248, ${(1 - d / 120) * 0.18})`;
            ctx.lineWidth = 1;
            ctx.stroke();
          }
        }
      }
      requestAnimationFrame(this.loop);
    }
  }

  // ----- Helpers -----
  function escapeHtml(str) {
    return String(str ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function animateCounters(root = document) {
    const nodes = $$(".stat-number", root);
    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          const el = entry.target;
          const target = Number(el.getAttribute("data-count") || 0);
          const start = performance.now();
          const dur = 1400;
          const tick = (now) => {
            const p = Math.min(1, (now - start) / dur);
            const eased = 1 - Math.pow(1 - p, 4);
            el.textContent = String(Math.floor(eased * target));
            if (p < 1) requestAnimationFrame(tick);
            else el.textContent = String(target);
          };
          requestAnimationFrame(tick);
          obs.unobserve(el);
        });
      },
      { threshold: 0.4 }
    );
    nodes.forEach((n) => obs.observe(n));
  }

  function setupReveal() {
    const els = $$(".feature-card, .shot-card, .plugin-card, .ai-card, .download-card, .docs-layout");
    els.forEach((el) => el.classList.add("reveal"));
    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("in");
            obs.unobserve(e.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
    );
    els.forEach((el) => obs.observe(el));
  }

  function setupNav() {
    const nav = $("#navbar");
    const links = $("#nav-links");
    const btn = $("#mobile-menu-btn");
    const toTop = $("#to-top");

    window.addEventListener("scroll", () => {
      nav.classList.toggle("scrolled", window.scrollY > 24);
      toTop.classList.toggle("show", window.scrollY > 420);
    });

    btn?.addEventListener("click", () => {
      links.classList.toggle("open");
      const icon = btn.querySelector("i");
      icon.className = links.classList.contains("open") ? "fas fa-times" : "fas fa-bars";
    });

    $$("#nav-links a").forEach((a) => {
      a.addEventListener("click", () => {
        links.classList.remove("open");
        const icon = btn?.querySelector("i");
        if (icon) icon.className = "fas fa-bars";
      });
    });

    // smooth anchors
    $$('a[href^="#"]').forEach((a) => {
      a.addEventListener("click", (e) => {
        const id = a.getAttribute("href");
        if (!id || id === "#") return;
        const target = document.querySelector(id);
        if (!target) return;
        e.preventDefault();
        const y = target.getBoundingClientRect().top + window.pageYOffset - 76;
        window.scrollTo({ top: y, behavior: "smooth" });
      });
    });

    // active section
    const sections = $$("section[id], header[id]");
    const navAs = $$("#nav-links a");
    window.addEventListener("scroll", () => {
      const y = window.pageYOffset;
      sections.forEach((sec) => {
        const top = sec.offsetTop - 110;
        const h = sec.offsetHeight;
        const id = sec.id;
        if (y >= top && y < top + h) {
          navAs.forEach((a) => {
            a.classList.toggle("active", a.getAttribute("href") === `#${id}`);
          });
        }
      });
    });

    toTop?.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));
  }

  function setupTheme() {
    const btn = $("#theme-toggle");
    const icon = btn?.querySelector("i");
    let theme = localStorage.getItem("bbot-site-theme") || "dark";
    const apply = () => {
      document.documentElement.setAttribute("data-theme", theme);
      if (icon) icon.className = theme === "dark" ? "fas fa-moon" : "fas fa-sun";
    };
    apply();
    btn?.addEventListener("click", () => {
      theme = theme === "dark" ? "light" : "dark";
      localStorage.setItem("bbot-site-theme", theme);
      apply();
    });
  }

  // ----- Render from config -----
  function renderHero(cfg) {
    const site = cfg.site || {};
    const hero = cfg.hero || {};
    document.title = `${site.name || "B-BOT"} - ${site.title || ""}`;
    $("#nav-version").textContent = `v${site.version || "1.1.2"}`;
    $("#hero-badge-text").textContent = hero.badge || "";
    if (Array.isArray(hero.title)) {
      $("#hero-title-0").textContent = hero.title[0] || "";
      $("#hero-title-1").textContent = hero.title[1] || "";
    }
    $("#hero-subtitle").textContent = hero.subtitle || site.description || "";

    const stats = $("#hero-stats");
    if (stats && Array.isArray(hero.stats)) {
      stats.innerHTML = hero.stats
        .map(
          (s) => `
        <div class="stat-item">
          <span class="stat-number" data-count="${Number(s.value) || 0}">0</span>
          <span class="stat-label">${escapeHtml(s.label || "")}</span>
        </div>`
        )
        .join("");
    }

    const actions = $("#hero-actions");
    if (actions && Array.isArray(hero.actions)) {
      actions.innerHTML = hero.actions
        .map((a) => {
          const cls = a.type === "primary" ? "btn btn-primary" : "btn btn-ghost";
          const ext = String(a.url || "").startsWith("http")
            ? ' target="_blank" rel="noopener"'
            : "";
          return `<a class="${cls}" href="${escapeHtml(a.url || "#")}"${ext}><i class="fas ${escapeHtml(
            a.icon || "fa-arrow-right"
          )}"></i> ${escapeHtml(a.text || "")}</a>`;
        })
        .join("");
    }
  }

  function renderFeatures(cfg) {
    const features = cfg.features || {};
    $("#features-title").textContent = features.title || "核心能力";
    $("#features-desc").textContent = features.description || "";

    const filters = $("#feature-filters");
    filters.innerHTML = (features.filters || [])
      .map(
        (f, i) =>
          `<button class="filter-btn${i === 0 ? " active" : ""}" type="button" data-filter="${escapeHtml(
            f.id
          )}">${escapeHtml(f.name)}</button>`
      )
      .join("");

    const grid = $("#features-grid");
    grid.innerHTML = (features.items || [])
      .map(
        (item) => `
      <article class="feature-card" data-category="${escapeHtml(item.category || "core")}">
        <div class="feature-icon"><i class="fas ${escapeHtml(item.icon || "fa-star")}"></i></div>
        <h3>${escapeHtml(item.title || "")}</h3>
        <p>${escapeHtml(item.description || "")}</p>
        <div class="feature-tags">
          ${(item.tags || []).map((t) => `<span class="tag">${escapeHtml(t)}</span>`).join("")}
        </div>
      </article>`
      )
      .join("");

    filters.addEventListener("click", (e) => {
      const btn = e.target.closest(".filter-btn");
      if (!btn) return;
      $$(".filter-btn", filters).forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const f = btn.getAttribute("data-filter");
      $$(".feature-card", grid).forEach((card) => {
        const cat = card.getAttribute("data-category");
        card.style.display = f === "all" || cat === f ? "" : "none";
      });
    });
  }

  function renderShowcase(cfg) {
    const sc = cfg.showcase || {};
    $("#showcase-title").textContent = sc.title || "界面预览";
    $("#showcase-desc").textContent = sc.description || "";
    const grid = $("#showcase-grid");
    grid.innerHTML = (sc.items || [])
      .map(
        (it) => `
      <article class="shot-card">
        <img src="${escapeHtml(it.image || "")}" alt="${escapeHtml(it.title || "")}" loading="lazy">
        <div class="shot-meta">
          <h3>${escapeHtml(it.title || "")}</h3>
          <p>${escapeHtml(it.desc || "")}</p>
        </div>
      </article>`
      )
      .join("");
  }

  function renderPlugins(cfg) {
    const pl = cfg.plugins || {};
    $("#plugins-title").textContent = pl.title || "插件";
    $("#plugins-desc").textContent = pl.description || "";
    const grid = $("#plugins-grid");
    grid.innerHTML = (pl.modes || [])
      .map((m, idx) => {
        const badgeCls = idx === 0 ? "mode-badge" : "mode-badge compat";
        return `
        <article class="plugin-card">
          <div class="plugin-head">
            <h3>${escapeHtml(m.name || "")}</h3>
            <span class="${badgeCls}">${escapeHtml(m.badge || "")}</span>
          </div>
          <div class="plugin-body">
            <p>${escapeHtml(m.description || "")}</p>
            <ul class="feature-list">
              ${(m.features || [])
                .map((f) => `<li><i class="fas fa-check"></i>${escapeHtml(f)}</li>`)
                .join("")}
            </ul>
            <div class="code-block">
              <div class="code-head">
                <span>python</span>
                <button class="copy-btn" type="button" title="复制"><i class="fas fa-copy"></i></button>
              </div>
              <pre><code>${escapeHtml(m.code || "")}</code></pre>
            </div>
          </div>
        </article>`;
      })
      .join("");
  }

  function renderAI(cfg) {
    const ai = cfg.ai || {};
    $("#ai-title").textContent = ai.title || "AI 大脑";
    $("#ai-desc").textContent = ai.description || "";
    $("#ai-grid").innerHTML = (ai.features || [])
      .map(
        (f) => `
      <article class="ai-card">
        <div class="ai-icon"><i class="fas ${escapeHtml(f.icon || "fa-star")}"></i></div>
        <h3>${escapeHtml(f.title || "")}</h3>
        <p>${escapeHtml(f.description || "")}</p>
      </article>`
      )
      .join("");
  }

  function renderDocs(cfg) {
    const docs = cfg.docs || {};
    $("#docs-title").textContent = docs.title || "上手";
    $("#docs-desc").textContent = docs.description || "";
    if (cfg.site?.docsUrl) $("#docs-more").href = cfg.site.docsUrl;

    const nav = $("#docs-nav");
    const panel = $("#docs-panel");
    const sections = docs.sections || {};
    const navigation = docs.navigation || [];

    const renderSection = (id) => {
      const sec = sections[id];
      if (!sec) {
        panel.innerHTML = "<p>暂无内容</p>";
        return;
      }
      const blocks = (sec.content || [])
        .map((block) => {
          if (block.type === "h4") {
            return `<div class="doc-block"><h4>${escapeHtml(block.text || "")}</h4></div>`;
          }
          if (block.type === "p") {
            return `<div class="doc-block"><p>${block.text || ""}</p></div>`;
          }
          if (block.type === "code") {
            return `
              <div class="doc-block">
                <div class="code-block">
                  <div class="code-head">
                    <span>${escapeHtml(block.language || "text")}</span>
                    <button class="copy-btn" type="button" title="复制"><i class="fas fa-copy"></i></button>
                  </div>
                  <pre><code>${escapeHtml(block.content || "")}</code></pre>
                </div>
              </div>`;
          }
          return "";
        })
        .join("");
      panel.innerHTML = `<h3>${escapeHtml(sec.title || id)}</h3>${blocks}`;
      bindCopy(panel);
    };

    nav.innerHTML = navigation
      .map(
        (n, i) => `
      <li>
        <button type="button" data-id="${escapeHtml(n.id)}" class="${i === 0 ? "active" : ""}">
          <i class="fas ${escapeHtml(n.icon || "fa-file")}"></i>
          ${escapeHtml(n.name || n.id)}
        </button>
      </li>`
      )
      .join("");

    nav.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-id]");
      if (!btn) return;
      $$("button", nav).forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      renderSection(btn.getAttribute("data-id"));
    });

    if (navigation[0]) renderSection(navigation[0].id);
  }

  function openDockerModal(cfg) {
    let mask = $("#docker-modal");
    if (!mask) {
      mask = document.createElement("div");
      mask.id = "docker-modal";
      mask.className = "modal-mask";
      mask.innerHTML = `
        <div class="modal" role="dialog" aria-modal="true" aria-labelledby="docker-modal-title">
          <div class="modal-h">
            <h3 id="docker-modal-title">Docker 部署命令</h3>
            <button class="icon-btn close-modal" type="button" aria-label="关闭"><i class="fas fa-times"></i></button>
          </div>
          <div class="modal-b">
            <p>把数据目录挂到 <code>/app/mount</code>。首次启动会自动初始化；已有数据请先备份。</p>
            <div class="code-block">
              <div class="code-head">
                <span>bash</span>
                <button class="copy-btn" type="button" title="复制"><i class="fas fa-copy"></i></button>
              </div>
              <pre><code id="docker-cmd"></code></pre>
            </div>
            <p style="margin-top:0.9rem;margin-bottom:0;">浏览器访问 <code>http://服务器IP:5000</code> 进入面板。</p>
          </div>
        </div>`;
      document.body.appendChild(mask);
      const close = () => mask.classList.remove("open");
      mask.addEventListener("click", (e) => {
        if (e.target === mask || e.target.closest(".close-modal")) close();
      });
      document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && mask.classList.contains("open")) close();
      });
    }
    const cmd =
      cfg.docs?.sections?.quickstart?.content?.find((x) => x.type === "code")?.content ||
      `docker run -d \\\n  --name bbot \\\n  --restart unless-stopped \\\n  -p 5000:5000 \\\n  -p 8888:8888 \\\n  -v /var/run/docker.sock:/var/run/docker.sock \\\n  -v /your/data/path:/app/mount \\\n  241793/b-bot:latest`;
    $("#docker-cmd", mask).textContent = cmd;
    bindCopy(mask);
    mask.classList.add("open");
  }

  function renderDownload(cfg) {
    const dl = cfg.download || {};
    $("#download-title").textContent = dl.title || "立即开始";
    $("#download-desc").textContent = dl.description || "";
    const grid = $("#download-grid");
    grid.innerHTML = (dl.options || [])
      .map((o) => {
        const isDocker = o.id === "docker" || String(o.button?.url || "") === "#docs";
        const href = o.button?.url || "#";
        const type = o.button?.type === "primary" ? "btn btn-primary" : "btn btn-ghost";
        const icon = String(o.icon || "").includes("fa-") ? o.icon : `fa-${o.icon || "box"}`;
        const brand = ["docker", "github", "android", "windows"].some((x) => icon.includes(x))
          ? "fab"
          : "fas";
        return `
        <article class="download-card">
          <div class="download-icon"><i class="${brand} ${escapeHtml(icon)}"></i></div>
          <h3>${escapeHtml(o.name || "")}</h3>
          <p>${escapeHtml(o.description || "")}</p>
          <div class="ver">${escapeHtml(o.version || "")}</div>
          <a class="${type} dl-btn" href="${escapeHtml(href)}" data-docker="${isDocker ? "1" : "0"}"${
          String(href).startsWith("http") ? ' target="_blank" rel="noopener"' : ""
        }>${escapeHtml(o.button?.text || "打开")}</a>
        </article>`;
      })
      .join("");

    grid.addEventListener("click", (e) => {
      const a = e.target.closest(".dl-btn");
      if (!a) return;
      if (a.getAttribute("data-docker") === "1") {
        e.preventDefault();
        openDockerModal(cfg);
      }
    });

    const cta = $("#cta-docker-btn");
    if (cta) {
      cta.addEventListener("click", (e) => {
        e.preventDefault();
        openDockerModal(cfg);
      });
    }
  }

  function renderFooter(cfg) {
    const ft = cfg.footer || {};
    $("#footer-tagline").textContent = cfg.site?.description || "AI 驱动的智能机器人框架";
    $("#footer-copy").textContent = ft.copyright || "© 2026 B-BOT";
    const cols = $("#footer-cols");
    cols.innerHTML = (ft.sections || [])
      .map(
        (s) => `
      <div class="footer-col">
        <h4>${escapeHtml(s.title || "")}</h4>
        <ul>
          ${(s.links || [])
            .map((l) => {
              const ext = String(l.url || "").startsWith("http")
                ? ' target="_blank" rel="noopener"'
                : "";
              return `<li><a href="${escapeHtml(l.url || "#")}"${ext}>${escapeHtml(l.name || "")}</a></li>`;
            })
            .join("")}
        </ul>
      </div>`
      )
      .join("");
  }

  function bindCopy(root = document) {
    $$(".copy-btn", root).forEach((btn) => {
      if (btn.dataset.bound) return;
      btn.dataset.bound = "1";
      btn.addEventListener("click", async () => {
        const block = btn.closest(".code-block");
        const code = block?.querySelector("code")?.textContent || "";
        try {
          await navigator.clipboard.writeText(code);
          const old = btn.innerHTML;
          btn.innerHTML = '<i class="fas fa-check"></i>';
          setTimeout(() => {
            btn.innerHTML = old;
          }, 1400);
        } catch (_) {}
      });
    });
  }

  async function main() {
    setupTheme();
    setupNav();
    const canvas = $("#particles-canvas");
    if (canvas) new Particles(canvas);

    let cfg = null;
    try {
      const res = await fetch("config.json", { cache: "no-store" });
      cfg = await res.json();
    } catch (e) {
      console.error("config.json load failed", e);
      cfg = { site: { name: "B-BOT", version: "1.1.2" } };
    }

    renderHero(cfg);
    renderFeatures(cfg);
    renderShowcase(cfg);
    renderPlugins(cfg);
    renderAI(cfg);
    renderDocs(cfg);
    renderDownload(cfg);
    renderFooter(cfg);

    animateCounters();
    setupReveal();
    bindCopy(document);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", main);
  } else {
    main();
  }
})();
