const menuToggle = document.querySelector("[data-menu-toggle]");
const menu = document.querySelector("[data-menu]");
const preloader = document.getElementById("phoenix-preloader");
const siteHeader = document.querySelector(".site-header");

if (siteHeader) {
  const updateHeaderState = () => {
    siteHeader.classList.toggle("is-scrolled", window.scrollY > 12);
  };

  updateHeaderState();
  window.addEventListener("scroll", updateHeaderState, { passive: true });
}

if (preloader) {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const navEntry = performance.getEntriesByType("navigation")[0];
  const isReload = navEntry && navEntry.type === "reload";
  const storage = {
    get() {
      try {
        return window.sessionStorage && window.sessionStorage.getItem("phoenixIntroSeen") === "true";
      } catch (error) {
        return false;
      }
    },
    set() {
      try {
        if (window.sessionStorage) {
          window.sessionStorage.setItem("phoenixIntroSeen", "true");
        }
      } catch (error) {
        return;
      }
    },
  };
  const hasSeenIntro = storage.get();
  const shouldPlayIntro = isReload || !hasSeenIntro;

  const revealSite = (skipAnimation = false) => {
    document.body.classList.remove("preloader-active");
    document.body.classList.add("site-revealed");
    storage.set();

    if (skipAnimation) {
      preloader.classList.add("is-skipped");
      return;
    }

    preloader.classList.add("is-leaving");
    window.setTimeout(() => {
      preloader.remove();
    }, reduceMotion ? 180 : 900);
  };

  if (!shouldPlayIntro) {
    revealSite(true);
  } else {
    const minDuration = reduceMotion ? 220 : 1450;
    const maxDuration = reduceMotion ? 700 : 2400;
    const startedAt = performance.now();
    let didReveal = false;

    const finish = () => {
      if (didReveal) return;
      didReveal = true;
      const elapsed = performance.now() - startedAt;
      const wait = Math.max(0, minDuration - elapsed);
      window.setTimeout(() => revealSite(false), wait);
    };

    if (document.readyState === "complete") {
      finish();
    } else {
      window.addEventListener("load", finish, { once: true });
    }

    window.setTimeout(finish, maxDuration);
  }
}

if (menuToggle && menu) {
  menuToggle.addEventListener("click", () => {
    menu.classList.toggle("is-open");
    menuToggle.setAttribute("aria-expanded", menu.classList.contains("is-open"));
  });
}

document.querySelectorAll(".nav-dropdown-toggle").forEach((toggle) => {
  toggle.addEventListener("click", () => {
    toggle.closest(".nav-dropdown").classList.toggle("is-open");
  });
});

document.querySelectorAll("[data-shop-catalog]").forEach((catalog) => {
  const trigger = catalog.querySelector("[data-shop-trigger]");
  const mainItems = catalog.querySelectorAll("[data-catalog-panel]");
  const panels = catalog.querySelectorAll("[data-catalog-panel-content]");
  const backButtons = catalog.querySelectorAll("[data-catalog-back]");
  let closeTimer;

  const isCompact = () => window.matchMedia("(max-width: 1100px)").matches;

  const setPanel = (panelName) => {
    mainItems.forEach((item) => {
      item.classList.toggle("is-active", item.dataset.catalogPanel === panelName);
    });
    panels.forEach((panel) => {
      panel.classList.toggle("is-active", panel.dataset.catalogPanelContent === panelName);
    });
  };

  const openCatalog = () => {
    window.clearTimeout(closeTimer);
    catalog.classList.add("is-open");
    trigger?.setAttribute("aria-expanded", "true");
  };

  const closeCatalog = () => {
    catalog.classList.remove("is-open", "is-panel-open");
    trigger?.setAttribute("aria-expanded", "false");
  };

  catalog.addEventListener("mouseenter", openCatalog);
  catalog.addEventListener("mouseleave", () => {
    closeTimer = window.setTimeout(closeCatalog, 220);
  });

  trigger?.addEventListener("keydown", (event) => {
    if (["Enter", " ", "ArrowDown"].includes(event.key)) {
      event.preventDefault();
      openCatalog();
      mainItems[0]?.focus();
    }
    if (event.key === "Escape") {
      closeCatalog();
    }
  });

  trigger?.addEventListener("click", (event) => {
    if (!isCompact()) return;
    event.preventDefault();
    catalog.classList.toggle("is-open");
    catalog.classList.remove("is-panel-open");
    trigger.setAttribute("aria-expanded", catalog.classList.contains("is-open"));
  });

  mainItems.forEach((item) => {
    const activate = () => {
      setPanel(item.dataset.catalogPanel);
      if (isCompact()) {
        catalog.classList.add("is-panel-open");
      }
    };
    item.addEventListener("mouseenter", activate);
    item.addEventListener("focus", activate);
    item.addEventListener("click", activate);
    item.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeCatalog();
        trigger?.focus();
      }
    });
  });

  backButtons.forEach((button) => {
    button.addEventListener("click", () => {
      catalog.classList.remove("is-panel-open");
      mainItems.forEach((item) => item.classList.remove("is-active"));
      panels.forEach((panel) => panel.classList.remove("is-active"));
    });
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeCatalog();
    }
  });
});

document.querySelectorAll("[data-chatbot]").forEach((chatbot) => {
  const launcher = chatbot.querySelector("[data-chatbot-launcher]");
  const panel = chatbot.querySelector("[data-chatbot-panel]");
  const closeButton = chatbot.querySelector("[data-chatbot-close]");
  const messages = chatbot.querySelector("[data-chatbot-messages]");
  const form = chatbot.querySelector("[data-chatbot-form]");
  const input = chatbot.querySelector("[data-chatbot-input]");
  const sendButton = chatbot.querySelector("[data-chatbot-send]");
  const quickActions = chatbot.querySelectorAll("[data-chatbot-action]");
  const endpoint = chatbot.dataset.endpoint;
  const csrfToken = chatbot.dataset.csrf;
  const history = [];
  let pending = false;
  let welcomed = false;
  let typingNode = null;

  const pageContext = () => {
    const productMatch = window.location.pathname.match(/^\/product\/([^/]+)\//);
    if (productMatch) {
      return { type: "product", slug: productMatch[1] };
    }
    const shopMatch = window.location.pathname.match(/^\/shop\/([^/]+)(?:\/([^/]+))?\//);
    if (shopMatch) {
      return { type: "category", main_slug: shopMatch[1], sub_slug: shopMatch[2] || "" };
    }
    return { type: "page", path: window.location.pathname };
  };

  const remember = (role, content) => {
    history.push({ role, content });
    while (history.length > 8) {
      history.shift();
    }
  };

  const scrollMessages = () => {
    messages.scrollTop = messages.scrollHeight;
  };

  const makeElement = (tagName, className, text) => {
    const node = document.createElement(tagName);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  };

  const addActions = (container, actions) => {
    if (!actions || !actions.length) return;
    const actionList = makeElement("div", "chatbot-actions");
    actions.forEach((action) => {
      if (!action || !action.label || !action.url) return;
      const link = makeElement("a", "", action.label);
      link.href = action.url;
      actionList.appendChild(link);
    });
    container.appendChild(actionList);
  };

  const addProducts = (container, products) => {
    if (!products || !products.length) return;
    const productList = makeElement("div", "chatbot-products");
    products.forEach((product) => {
      if (!product || !product.name || !product.url) return;
      const card = makeElement("a", "chatbot-product");
      card.href = product.url;

      if (product.image) {
        const image = document.createElement("img");
        image.src = product.image;
        image.alt = product.name;
        card.appendChild(image);
      } else {
        card.appendChild(makeElement("span", "chatbot-product-placeholder", "P"));
      }

      const body = makeElement("span", "");
      body.appendChild(makeElement("strong", "", product.name));
      if (product.price) body.appendChild(makeElement("small", "", product.price));
      if (product.availability) body.appendChild(makeElement("small", "", product.availability));
      card.appendChild(body);
      productList.appendChild(card);
    });
    container.appendChild(productList);
  };

  const addMessage = (role, text, options = {}) => {
    const message = makeElement("div", `chatbot-message is-${role}`);
    const bubble = makeElement("div", "chatbot-bubble", text);
    message.appendChild(bubble);
    addProducts(message, options.products);
    addActions(message, options.actions);
    messages.appendChild(message);
    scrollMessages();
    return message;
  };

  const showTyping = () => {
    typingNode = makeElement("div", "chatbot-message is-assistant");
    const bubble = makeElement("div", "chatbot-bubble");
    bubble.appendChild(document.createTextNode("Phoenix Assistant is typing"));
    const dots = makeElement("span", "chatbot-typing");
    dots.setAttribute("aria-hidden", "true");
    dots.appendChild(document.createElement("span"));
    dots.appendChild(document.createElement("span"));
    dots.appendChild(document.createElement("span"));
    bubble.appendChild(dots);
    typingNode.appendChild(bubble);
    messages.appendChild(typingNode);
    scrollMessages();
  };

  const hideTyping = () => {
    if (typingNode) {
      typingNode.remove();
      typingNode = null;
    }
  };

  const setPending = (isPending) => {
    pending = isPending;
    input.disabled = isPending;
    sendButton.disabled = isPending;
  };

  const welcome = () => {
    if (welcomed) return;
    welcomed = true;
    addMessage(
      "assistant",
      "Hi 👋 Welcome to Phoenix Interior Hub. I can help you find products, explore our catalogue and navigate the store. What are you looking for?"
    );
  };

  const openChatbot = () => {
    panel.hidden = false;
    chatbot.classList.add("is-open", "has-used");
    launcher.setAttribute("aria-expanded", "true");
    welcome();
    window.setTimeout(() => input.focus(), 80);
  };

  const closeChatbot = () => {
    panel.hidden = true;
    chatbot.classList.remove("is-open");
    launcher.setAttribute("aria-expanded", "false");
    launcher.focus();
  };

  const submitMessage = async (message) => {
    const trimmed = message.trim();
    if (!trimmed || pending) return;

    addMessage("user", trimmed);
    remember("user", trimmed);
    input.value = "";
    input.style.height = "";
    setPending(true);
    showTyping();

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        credentials: "same-origin",
        body: JSON.stringify({
          message: trimmed,
          history,
          page_context: pageContext(),
        }),
      });
      const payload = await response.json();
      hideTyping();
      const reply = payload.message || "Sorry, I couldn't process that request. Please try again.";
      addMessage("assistant", reply, { products: payload.products || [], actions: payload.actions || [] });
      remember("assistant", reply);
    } catch (error) {
      hideTyping();
      const reply = "Sorry, I couldn't process that request. Please try again.";
      addMessage("assistant", reply);
      remember("assistant", reply);
    } finally {
      setPending(false);
      input.focus();
    }
  };

  launcher?.addEventListener("click", () => {
    if (panel.hidden) {
      openChatbot();
    } else {
      closeChatbot();
    }
  });

  closeButton?.addEventListener("click", closeChatbot);

  quickActions.forEach((button) => {
    button.addEventListener("click", () => {
      const targetUrl = button.dataset.url;
      if (targetUrl) {
        window.location.href = targetUrl;
        return;
      }
      openChatbot();
      submitMessage(button.dataset.message || button.textContent || "");
    });
  });

  input?.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 94)}px`;
  });

  input?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
    if (event.key === "Escape") {
      closeChatbot();
    }
  });

  form?.addEventListener("submit", (event) => {
    event.preventDefault();
    submitMessage(input.value);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !panel.hidden) {
      closeChatbot();
    }
  });
});
