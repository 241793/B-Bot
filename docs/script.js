// ===== Particle Background =====
class ParticleSystem {
    constructor() {
        this.canvas = document.getElementById('particles-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.particles = [];
        this.maxParticles = 100;
        this.connectionDistance = 150;
        this.maxConnections = 3;
        
        this.init();
    }
    
    init() {
        this.resize();
        this.createParticles();
        this.animate();
        
        window.addEventListener('resize', () => this.resize());
    }
    
    resize() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
    }
    
    createParticles() {
        for (let i = 0; i < this.maxParticles; i++) {
            this.particles.push({
                x: Math.random() * this.canvas.width,
                y: Math.random() * this.canvas.height,
                vx: (Math.random() - 0.5) * 0.5,
                vy: (Math.random() - 0.5) * 0.5,
                radius: Math.random() * 2 + 1,
                opacity: Math.random() * 0.5 + 0.2
            });
        }
    }
    
    animate() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Update and draw particles
        this.particles.forEach((particle, i) => {
            // Update position
            particle.x += particle.vx;
            particle.y += particle.vy;
            
            // Wrap around edges
            if (particle.x < 0) particle.x = this.canvas.width;
            if (particle.x > this.canvas.width) particle.x = 0;
            if (particle.y < 0) particle.y = this.canvas.height;
            if (particle.y > this.canvas.height) particle.y = 0;
            
            // Draw particle
            this.ctx.beginPath();
            this.ctx.arc(particle.x, particle.y, particle.radius, 0, Math.PI * 2);
            this.ctx.fillStyle = `rgba(0, 212, 255, ${particle.opacity})`;
            this.ctx.fill();
            
            // Draw connections
            let connections = 0;
            for (let j = i + 1; j < this.particles.length; j++) {
                if (connections >= this.maxConnections) break;
                
                const other = this.particles[j];
                const dx = particle.x - other.x;
                const dy = particle.y - other.y;
                const distance = Math.sqrt(dx * dx + dy * dy);
                
                if (distance < this.connectionDistance) {
                    const opacity = (1 - distance / this.connectionDistance) * 0.3;
                    this.ctx.beginPath();
                    this.ctx.moveTo(particle.x, particle.y);
                    this.ctx.lineTo(other.x, other.y);
                    this.ctx.strokeStyle = `rgba(0, 212, 255, ${opacity})`;
                    this.ctx.lineWidth = 0.5;
                    this.ctx.stroke();
                    connections++;
                }
            }
        });
        
        requestAnimationFrame(() => this.animate());
    }
}

// ===== Counter Animation =====
class CounterAnimation {
    constructor() {
        this.counters = document.querySelectorAll('.stat-number');
        this.duration = 2000;
        this.init();
    }
    
    init() {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    this.animate(entry.target);
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.5 });
        
        this.counters.forEach(counter => observer.observe(counter));
    }
    
    animate(counter) {
        const target = parseInt(counter.getAttribute('data-count'));
        const start = 0;
        const startTime = performance.now();
        
        const update = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / this.duration, 1);
            
            // Easing function
            const easeOutQuart = 1 - Math.pow(1 - progress, 4);
            const current = Math.floor(easeOutQuart * (target - start) + start);
            
            counter.textContent = current;
            
            if (progress < 1) {
                requestAnimationFrame(update);
            } else {
                counter.textContent = target;
            }
        };
        
        requestAnimationFrame(update);
    }
}

// ===== Feature Filter =====
class FeatureFilter {
    constructor() {
        this.filterBtns = document.querySelectorAll('.filter-btn');
        this.featureCards = document.querySelectorAll('.feature-card');
        this.init();
    }
    
    init() {
        this.filterBtns.forEach(btn => {
            btn.addEventListener('click', () => this.filter(btn));
        });
    }
    
    filter(activeBtn) {
        const filter = activeBtn.getAttribute('data-filter');
        
        // Update active button
        this.filterBtns.forEach(btn => btn.classList.remove('active'));
        activeBtn.classList.add('active');
        
        // Filter cards
        this.featureCards.forEach(card => {
            const category = card.getAttribute('data-category');
            
            if (filter === 'all' || category === filter) {
                card.style.display = 'block';
                card.style.animation = 'fadeInUp 0.6s ease-out forwards';
            } else {
                card.style.display = 'none';
            }
        });
    }
}

// ===== Theme Toggle =====
class ThemeToggle {
    constructor() {
        this.toggle = document.getElementById('theme-toggle');
        this.icon = this.toggle.querySelector('i');
        this.currentTheme = localStorage.getItem('theme') || 'dark';
        this.init();
    }
    
    init() {
        document.documentElement.setAttribute('data-theme', this.currentTheme);
        this.updateIcon();
        
        this.toggle.addEventListener('click', () => this.toggleTheme());
    }
    
    toggleTheme() {
        this.currentTheme = this.currentTheme === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', this.currentTheme);
        localStorage.setItem('theme', this.currentTheme);
        this.updateIcon();
    }
    
    updateIcon() {
        this.icon.className = this.currentTheme === 'dark' ? 'fas fa-moon' : 'fas fa-sun';
    }
}

// ===== Mobile Menu =====
class MobileMenu {
    constructor() {
        this.menuBtn = document.getElementById('mobile-menu-btn');
        this.navLinks = document.querySelector('.nav-links');
        this.init();
    }
    
    init() {
        this.menuBtn.addEventListener('click', () => this.toggle());
        
        // Close menu when clicking a link
        document.querySelectorAll('.nav-links a').forEach(link => {
            link.addEventListener('click', () => this.close());
        });
    }
    
    toggle() {
        this.navLinks.classList.toggle('active');
        const icon = this.menuBtn.querySelector('i');
        icon.className = this.navLinks.classList.contains('active') ? 'fas fa-times' : 'fas fa-bars';
    }
    
    close() {
        this.navLinks.classList.remove('active');
        this.menuBtn.querySelector('i').className = 'fas fa-bars';
    }
}

// ===== Smooth Scroll =====
class SmoothScroll {
    constructor() {
        this.links = document.querySelectorAll('a[href^="#"]');
        this.init();
    }
    
    init() {
        this.links.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const target = document.querySelector(link.getAttribute('href'));
                if (target) {
                    const offset = 80; // Navbar height
                    const targetPosition = target.getBoundingClientRect().top + window.pageYOffset - offset;
                    window.scrollTo({
                        top: targetPosition,
                        behavior: 'smooth'
                    });
                }
            });
        });
    }
}

// ===== Navbar Scroll Effect =====
class NavbarScroll {
    constructor() {
        this.navbar = document.querySelector('.navbar');
        this.init();
    }
    
    init() {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 50) {
                this.navbar.style.background = 'rgba(10, 10, 15, 0.95)';
                this.navbar.style.boxShadow = '0 4px 20px rgba(0, 0, 0, 0.3)';
            } else {
                this.navbar.style.background = 'rgba(10, 10, 15, 0.8)';
                this.navbar.style.boxShadow = 'none';
            }
        });
    }
}

// ===== Active Section Highlight =====
class ActiveSection {
    constructor() {
        this.sections = document.querySelectorAll('section[id]');
        this.navLinks = document.querySelectorAll('.nav-links a');
        this.init();
    }
    
    init() {
        window.addEventListener('scroll', () => this.highlight());
    }
    
    highlight() {
        const scrollY = window.pageYOffset;
        
        this.sections.forEach(section => {
            const sectionHeight = section.offsetHeight;
            const sectionTop = section.offsetTop - 100;
            const sectionId = section.getAttribute('id');
            
            if (scrollY > sectionTop && scrollY <= sectionTop + sectionHeight) {
                this.navLinks.forEach(link => {
                    link.classList.remove('active');
                    if (link.getAttribute('href') === `#${sectionId}`) {
                        link.classList.add('active');
                    }
                });
            }
        });
    }
}

// ===== Copy Code =====
class CopyCode {
    constructor() {
        this.copyBtns = document.querySelectorAll('.copy-btn');
        this.init();
    }
    
    init() {
        this.copyBtns.forEach(btn => {
            btn.addEventListener('click', () => this.copy(btn));
        });
    }
    
    copy(btn) {
        const codeBlock = btn.closest('.code-block') || btn.closest('.code-preview');
        const code = codeBlock.querySelector('code').textContent;
        
        navigator.clipboard.writeText(code).then(() => {
            const originalIcon = btn.innerHTML;
            btn.innerHTML = '<i class="fas fa-check"></i>';
            btn.style.color = '#00d4ff';
            
            setTimeout(() => {
                btn.innerHTML = originalIcon;
                btn.style.color = '';
            }, 2000);
        });
    }
}

// ===== Docs Navigation =====
class DocsNavigation {
    constructor() {
        this.docsNavItems = document.querySelectorAll('.docs-nav-item');
        this.docSections = document.querySelectorAll('.doc-section');
        this.init();
    }
    
    init() {
        this.docsNavItems.forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const targetId = item.querySelector('a').getAttribute('href');
                this.navigate(targetId);
                this.setActive(item);
            });
        });
    }
    
    navigate(targetId) {
        const target = document.querySelector(targetId);
        if (target) {
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }
    
    setActive(activeItem) {
        this.docsNavItems.forEach(item => item.classList.remove('active'));
        activeItem.classList.add('active');
    }
}

// ===== Scroll Reveal Animation =====
class ScrollReveal {
    constructor() {
        this.elements = document.querySelectorAll('.feature-card, .ai-card, .plugin-mode-card, .download-card');
        this.init();
    }
    
    init() {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.style.opacity = '1';
                    entry.target.style.transform = 'translateY(0)';
                }
            });
        }, {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        });
        
        this.elements.forEach(el => {
            el.style.opacity = '0';
            el.style.transform = 'translateY(30px)';
            el.style.transition = 'opacity 0.6s ease-out, transform 0.6s ease-out';
            observer.observe(el);
        });
    }
}

// ===== Typing Effect =====
class TypingEffect {
    constructor() {
        this.element = document.querySelector('.hero-subtitle');
        this.text = this.element ? this.element.textContent : '';
        this.speed = 50;
        this.init();
    }
    
    init() {
        if (!this.element) return;
        
        this.element.textContent = '';
        this.element.style.borderRight = '2px solid #00d4ff';
        this.element.style.paddingRight = '5px';
        
        let i = 0;
        const type = () => {
            if (i < this.text.length) {
                this.element.textContent += this.text.charAt(i);
                i++;
                setTimeout(type, this.speed);
            } else {
                // Remove cursor after typing
                setTimeout(() => {
                    this.element.style.borderRight = 'none';
                }, 1000);
            }
        };
        
        // Start typing after a delay
        setTimeout(type, 500);
    }
}

// ===== Config Loader =====
class ConfigLoader {
    constructor() {
        this.config = null;
    }
    
    async load() {
        try {
            const response = await fetch('config.json');
            if (!response.ok) {
                throw new Error('Failed to load config');
            }
            this.config = await response.json();
            this.renderContent();
            return this.config;
        } catch (error) {
            console.error('Error loading config:', error);
            return null;
        }
    }
    
    renderContent() {
        if (!this.config) return;
        
        // Update site title
        document.title = `${this.config.site.name} - ${this.config.site.title}`;
        
        // Update hero section
        this.updateHeroSection();
        
        // Update features section
        this.updateFeaturesSection();
        
        // Update plugins section
        this.updatePluginsSection();
        
        // Update AI section
        this.updateAISection();
        
        // Update docs section
        this.updateDocsSection();
        
        // Update download section
        this.updateDownloadSection();
        
        // Update footer
        this.updateFooter();
    }
    
    updateHeroSection() {
        const hero = this.config.hero;
        if (!hero) return;
        
        // Update badge
        const badge = document.querySelector('.hero-badge span:last-child');
        if (badge) badge.textContent = hero.badge;
        
        // Update title
        const titleLines = document.querySelectorAll('.hero-title .title-line');
        if (titleLines.length >= 2) {
            titleLines[0].textContent = hero.title[0];
            titleLines[1].textContent = hero.title[1];
        }
        
        // Update subtitle
        const subtitle = document.querySelector('.hero-subtitle');
        if (subtitle) subtitle.textContent = hero.subtitle;
        
        // Update stats
        const statItems = document.querySelectorAll('.hero-stats .stat-item');
        hero.stats.forEach((stat, index) => {
            if (statItems[index]) {
                const number = statItems[index].querySelector('.stat-number');
                const label = statItems[index].querySelector('.stat-label');
                if (number) {
                    number.textContent = '0';
                    number.setAttribute('data-count', stat.value);
                }
                if (label) label.textContent = stat.label;
            }
        });
        
        // Update actions
        const actionButtons = document.querySelectorAll('.hero-actions .btn');
        hero.actions.forEach((action, index) => {
            if (actionButtons[index]) {
                actionButtons[index].textContent = action.text;
                actionButtons[index].href = action.url;
                actionButtons[index].className = `btn btn-${action.type}`;
                actionButtons[index].innerHTML = `<i class="fas ${action.icon}"></i>${action.text}`;
            }
        });
    }
    
    updateFeaturesSection() {
        const features = this.config.features;
        if (!features) return;
        
        // Update section header
        const sectionHeader = document.querySelector('.features .section-header');
        if (sectionHeader) {
            const title = sectionHeader.querySelector('.section-title');
            const desc = sectionHeader.querySelector('.section-desc');
            if (title) title.textContent = features.title;
            if (desc) desc.textContent = features.description;
        }
        
        // Update filter buttons
        const filterBtns = document.querySelectorAll('.filter-tabs .filter-btn');
        features.filters.forEach((filter, index) => {
            if (filterBtns[index]) {
                filterBtns[index].textContent = filter.name;
                filterBtns[index].setAttribute('data-filter', filter.id);
            }
        });
        
        // Update feature cards
        const featuresGrid = document.querySelector('.features-grid');
        if (featuresGrid) {
            featuresGrid.innerHTML = '';
            features.items.forEach(item => {
                const card = document.createElement('div');
                card.className = 'feature-card';
                card.setAttribute('data-category', item.category);
                
                const tagsHtml = item.tags.map(tag => `<span class="tag">${tag}</span>`).join('');
                
                card.innerHTML = `
                    <div class="feature-icon">
                        <i class="fas ${item.icon}"></i>
                    </div>
                    <h3>${item.title}</h3>
                    <p>${item.description}</p>
                    <div class="feature-tags">
                        ${tagsHtml}
                    </div>
                `;
                
                featuresGrid.appendChild(card);
            });
        }
    }
    
    updatePluginsSection() {
        const plugins = this.config.plugins;
        if (!plugins) return;
        
        // Update section header
        const sectionHeader = document.querySelector('.plugins .section-header');
        if (sectionHeader) {
            const title = sectionHeader.querySelector('.section-title');
            const desc = sectionHeader.querySelector('.section-desc');
            if (title) title.textContent = plugins.title;
            if (desc) desc.textContent = plugins.description;
        }
        
        // Update plugin mode cards
        const pluginsShowcase = document.querySelector('.plugins-showcase');
        if (pluginsShowcase) {
            pluginsShowcase.innerHTML = '';
            plugins.modes.forEach(mode => {
                const card = document.createElement('div');
                card.className = 'plugin-mode-card';
                
                const featuresHtml = mode.features.map(feature => `<li><i class="fas fa-check"></i> ${feature}</li>`).join('');
                
                card.innerHTML = `
                    <div class="mode-header">
                        <span class="mode-badge ${mode.badge === '推荐' ? 'recommended' : 'compatible'}">${mode.badge}</span>
                        <h3>${mode.name}</h3>
                    </div>
                    <div class="mode-content">
                        <p>${mode.description}</p>
                        <ul class="feature-list">
                            ${featuresHtml}
                        </ul>
                    </div>
                    <div class="code-preview">
                        <pre><code class="language-python">${mode.code}</code></pre>
                    </div>
                `;
                
                pluginsShowcase.appendChild(card);
            });
        }
    }
    
    updateAISection() {
        const ai = this.config.ai;
        if (!ai) return;
        
        // Update section header
        const sectionHeader = document.querySelector('.ai-brain .section-header');
        if (sectionHeader) {
            const title = sectionHeader.querySelector('.section-title');
            const desc = sectionHeader.querySelector('.section-desc');
            if (title) title.textContent = ai.title;
            if (desc) desc.textContent = ai.description;
        }
        
        // Update AI feature cards
        const aiFeatures = document.querySelector('.ai-features');
        if (aiFeatures) {
            aiFeatures.innerHTML = '';
            ai.features.forEach(feature => {
                const card = document.createElement('div');
                card.className = 'ai-card';
                
                card.innerHTML = `
                    <div class="ai-icon">
                        <i class="fas ${feature.icon}"></i>
                    </div>
                    <h3>${feature.title}</h3>
                    <p>${feature.description}</p>
                `;
                
                aiFeatures.appendChild(card);
            });
        }
    }
    
    updateDocsSection() {
        const docs = this.config.docs;
        if (!docs) return;
        
        // Update section header
        const sectionHeader = document.querySelector('.docs .section-header');
        if (sectionHeader) {
            const title = sectionHeader.querySelector('.section-title');
            const desc = sectionHeader.querySelector('.section-desc');
            if (title) title.textContent = docs.title;
            if (desc) desc.textContent = docs.description;
        }
        
        // Update docs navigation
        const docsNav = document.querySelector('.docs-nav');
        if (docsNav) {
            docsNav.innerHTML = '';
            docs.navigation.forEach(item => {
                const navItem = document.createElement('li');
                navItem.className = 'docs-nav-item';
                navItem.innerHTML = `
                    <a href="#${item.id}">
                        <i class="fas ${item.icon}"></i>
                        ${item.name}
                    </a>
                `;
                docsNav.appendChild(navItem);
            });
        }
        
        // Update docs content
        const docsContent = document.querySelector('.docs-content');
        if (docsContent) {
            docsContent.innerHTML = '';
            Object.entries(docs.sections).forEach(([id, section]) => {
                const sectionDiv = document.createElement('div');
                sectionDiv.className = 'doc-section';
                sectionDiv.id = id;
                
                let contentHtml = `<h3>${section.title}</h3><div class="doc-content">`;
                
                section.content.forEach(item => {
                    if (item.type === 'h4') {
                        contentHtml += `<h4>${item.text}</h4>`;
                    } else if (item.type === 'p') {
                        contentHtml += `<p>${item.text}</p>`;
                    } else if (item.type === 'code') {
                        contentHtml += `
                            <div class="code-block">
                                <div class="code-header">
                                    <span>${item.language || ''}</span>
                                    <button class="copy-btn"><i class="fas fa-copy"></i></button>
                                </div>
                                <pre><code>${item.content}</code></pre>
                            </div>
                        `;
                    }
                });
                
                contentHtml += `</div>`;
                sectionDiv.innerHTML = contentHtml;
                docsContent.appendChild(sectionDiv);
            });
        }
    }
    
    updateDownloadSection() {
        const download = this.config.download;
        if (!download) return;
        
        // Update section header
        const sectionHeader = document.querySelector('.download .section-header');
        if (sectionHeader) {
            const title = sectionHeader.querySelector('.section-title');
            const desc = sectionHeader.querySelector('.section-desc');
            if (title) title.textContent = download.title;
            if (desc) desc.textContent = download.description;
        }
        
        // Update download options
        const downloadOptions = document.querySelector('.download-options');
        if (downloadOptions) {
            downloadOptions.innerHTML = '';
            download.options.forEach(option => {
                const card = document.createElement('div');
                card.className = 'download-card';
                
                card.innerHTML = `
                    <div class="download-icon">
                        <i class="fab ${option.icon}"></i>
                    </div>
                    <h3>${option.name}</h3>
                    <p>${option.description}</p>
                    <span class="version">${option.version}</span>
                    <a href="${option.button.url}" class="btn btn-${option.button.type}">
                        ${option.button.text}
                    </a>
                `;
                
                downloadOptions.appendChild(card);
            });
        }
    }
    
    updateFooter() {
        const footer = this.config.footer;
        if (!footer) return;
        
        // Update footer links
        const footerLinks = document.querySelector('.footer-links');
        if (footerLinks) {
            footerLinks.innerHTML = '';
            footer.sections.forEach(section => {
                const sectionDiv = document.createElement('div');
                sectionDiv.className = 'footer-section';
                
                const linksHtml = section.links.map(link => `<li><a href="${link.url}">${link.name}</a></li>`).join('');
                
                sectionDiv.innerHTML = `
                    <h4>${section.title}</h4>
                    <ul>
                        ${linksHtml}
                    </ul>
                `;
                
                footerLinks.appendChild(sectionDiv);
            });
        }
        
        // Update copyright
        const copyright = document.querySelector('.footer-bottom p');
        if (copyright) copyright.textContent = footer.copyright;
    }
}

// ===== Initialize All =====
document.addEventListener('DOMContentLoaded', async () => {
    // Load config
    const configLoader = new ConfigLoader();
    await configLoader.load();
    
    // Initialize particle system
    new ParticleSystem();
    
    // Initialize counter animation
    new CounterAnimation();
    
    // Initialize feature filter
    new FeatureFilter();
    
    // Initialize theme toggle
    new ThemeToggle();
    
    // Initialize mobile menu
    new MobileMenu();
    
    // Initialize smooth scroll
    new SmoothScroll();
    
    // Initialize navbar scroll effect
    new NavbarScroll();
    
    // Initialize active section highlight
    new ActiveSection();
    
    // Initialize copy code
    new CopyCode();
    
    // Initialize docs navigation
    new DocsNavigation();
    
    // Initialize scroll reveal
    new ScrollReveal();
    
    // Initialize typing effect
    new TypingEffect();
    
    // Fix click events
    fixClickEvents();
});

// ===== Modal for Docker Command =====
class DockerModal {
    constructor() {
        this.modal = null;
        this.createModal();
    }
    
    createModal() {
        // Create modal element
        this.modal = document.createElement('div');
        this.modal.className = 'docker-modal';
        this.modal.style.display = 'none';
        this.modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Docker 部署指令</h3>
                    <button class="close-btn">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="code-block">
                        <div class="code-header">
                            <span>bash</span>
                            <button class="copy-btn"><i class="fas fa-copy"></i> 复制</button>
                        </div>
                        <pre><code class="language-bash">docker run -d \
  --name bbot \
  --restart unless-stopped \
  -p 5000:5000 \
  -p 8888:8888 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /your/data/path:/app/mount \
  241793/b-bot:latest</code></pre>
                    </div>
                    <div class="modal-note">
                        <p><strong>注意：</strong>请将 <code>/your/data/path</code> 替换为您的实际数据目录路径</p>
                    </div>
                </div>
            </div>
        `;
        
        // Add to document
        document.body.appendChild(this.modal);
        
        // Add event listeners
        this.addEventListeners();
    }
    
    addEventListeners() {
        // Close button
        const closeBtn = this.modal.querySelector('.close-btn');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.hide());
        }
        
        // Copy button
        const copyBtn = this.modal.querySelector('.copy-btn');
        if (copyBtn) {
            copyBtn.addEventListener('click', () => this.copyCommand());
        }
        
        // Click outside to close
        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) {
                this.hide();
            }
        });
    }
    
    show() {
        this.modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }
    
    hide() {
        this.modal.style.display = 'none';
        document.body.style.overflow = 'auto';
    }
    
    copyCommand() {
        const code = this.modal.querySelector('code');
        if (code) {
            const text = code.textContent;
            navigator.clipboard.writeText(text).then(() => {
                const copyBtn = this.modal.querySelector('.copy-btn');
                if (copyBtn) {
                    const originalText = copyBtn.innerHTML;
                    copyBtn.innerHTML = '<i class="fas fa-check"></i> 已复制';
                    copyBtn.style.color = '#00d4ff';
                    
                    setTimeout(() => {
                        copyBtn.innerHTML = originalText;
                        copyBtn.style.color = '';
                    }, 2000);
                }
            });
        }
    }
}

// ===== Fix Click Events =====
function fixClickEvents() {
    // Initialize docker modal
    const dockerModal = new DockerModal();
    
    // Fix download buttons
    document.querySelectorAll('.download-card a').forEach(btn => {
        btn.addEventListener('click', function(e) {
            const href = this.getAttribute('href');
            if (href === 'docker') {
                e.preventDefault();
                dockerModal.show();
            } else if (href === '#') {
                e.preventDefault();
                alert('此功能正在开发中，敬请期待！');
            }
        });
    });
    
    // Fix docs navigation
    document.querySelectorAll('.docs-nav-item a').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            const target = document.querySelector(targetId);
            if (target) {
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                
                // Update active state
                document.querySelectorAll('.docs-nav-item').forEach(item => item.classList.remove('active'));
                this.closest('.docs-nav-item').classList.add('active');
            }
        });
    });
    
    // Fix footer links
    document.querySelectorAll('.footer-section a').forEach(link => {
        link.addEventListener('click', function(e) {
            const href = this.getAttribute('href');
            if (href === '#') {
                e.preventDefault();
                alert('此功能正在开发中，敬请期待！');
            }
        });
    });
    
    // Fix feature filter buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            // This is already handled by FeatureFilter class
            // Just ensuring it's working
            console.log('Filter button clicked:', this.getAttribute('data-filter'));
        });
    });
    
    // Fix theme toggle
    document.getElementById('theme-toggle').addEventListener('click', function() {
        console.log('Theme toggle clicked');
    });
    
    // Fix mobile menu button
    document.getElementById('mobile-menu-btn').addEventListener('click', function() {
        console.log('Mobile menu button clicked');
    });
}

// ===== Parallax Effect =====
window.addEventListener('scroll', () => {
    const scrolled = window.pageYOffset;
    const parallaxElements = document.querySelectorAll('.robot-container');
    
    parallaxElements.forEach(el => {
        const speed = 0.5;
        el.style.transform = `translateY(${scrolled * speed}px)`;
    });
});

// ===== Mouse Follow Effect =====
document.addEventListener('mousemove', (e) => {
    const cards = document.querySelectorAll('.feature-card, .ai-card');
    
    cards.forEach(card => {
        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        if (x >= 0 && x <= rect.width && y >= 0 && y <= rect.height) {
            const centerX = rect.width / 2;
            const centerY = rect.height / 2;
            const rotateX = (y - centerY) / 20;
            const rotateY = (centerX - x) / 20;
            
            card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateZ(10px)`;
        } else {
            card.style.transform = 'perspective(1000px) rotateX(0) rotateY(0) translateZ(0)';
        }
    });
});
