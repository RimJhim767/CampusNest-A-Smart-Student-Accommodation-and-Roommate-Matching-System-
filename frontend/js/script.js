/* =========================================================
   CampusNest — Shared JavaScript
   This file is loaded on every page. Each section checks
   that the element it needs exists before using it, so the
   same file works everywhere without throwing errors.
   ========================================================= */

document.addEventListener("DOMContentLoaded", function () {
  initMobileNav();
  initAuthNav();
  initPasswordToggles();
  initRegisterForm();
  initLoginForm();
  initProfileForm();
  initPreferencesForm();
  initMatchFilters();
  initMatchesPage();
  initMatchProfilePage();
  initRequestsPage();
});

/* ---------------------------------------------------------
   Mobile navigation menu
   --------------------------------------------------------- */
function initMobileNav() {
  const toggle = document.querySelector(".nav-toggle");
  const links = document.querySelector(".nav-links");
  if (!toggle || !links) return;

  toggle.addEventListener("click", function () {
    links.classList.toggle("open");
    const expanded = links.classList.contains("open");
    toggle.setAttribute("aria-expanded", String(expanded));
  });
}

/* ---------------------------------------------------------
   Password show/hide toggles
   Works for any .password-field on the page.
   --------------------------------------------------------- */
function initPasswordToggles() {
  const toggles = document.querySelectorAll(".password-toggle");
  if (!toggles.length) return;

  toggles.forEach(function (btn) {
    btn.addEventListener("click", function () {
      const targetId = btn.getAttribute("data-target");
      const input = document.getElementById(targetId);
      if (!input) return;
      const isHidden = input.type === "password";
      input.type = isHidden ? "text" : "password";
      btn.textContent = isHidden ? "Hide" : "Show";
    });
  });
}

/* ---------------------------------------------------------
   Small validation helpers, reused by every form
   --------------------------------------------------------- */
function setFieldError(fieldEl, message) {
  if (!fieldEl) return;
  fieldEl.classList.add("has-error");
  const errorEl = fieldEl.querySelector(".field-error");
  if (errorEl) errorEl.textContent = message;
}

function clearFieldError(fieldEl) {
  if (!fieldEl) return;
  fieldEl.classList.remove("has-error");
}

function clearAllErrors(form) {
  form.querySelectorAll(".field.has-error").forEach(function (f) {
    clearFieldError(f);
  });
}

/* ---------------------------------------------------------
   Register form
   --------------------------------------------------------- */
function initRegisterForm() {
  const form = document.getElementById("register-form");
  if (!form) return;

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    clearAllErrors(form);
    let valid = true;

    const name = form.querySelector("#full-name");
    const email = form.querySelector("#niter-email");
    const password = form.querySelector("#password");
    const confirm = form.querySelector("#confirm-password");

    if (!name.value.trim()) {
      setFieldError(name.closest(".field"), "Please enter your full name.");
      valid = false;
    }
    if (!email.value.trim()) {
      setFieldError(email.closest(".field"), "Please enter your NITER email.");
      valid = false;
    }
    if (!password.value.trim() || password.value.length < 6) {
      setFieldError(password.closest(".field"), "Password must be at least 6 characters.");
      valid = false;
    }
    if (confirm.value !== password.value || !confirm.value.trim()) {
      setFieldError(confirm.closest(".field"), "Passwords do not match.");
      valid = false;
    }

    if (!valid) return;

    // Send the data to the Flask backend
    const submitBtn = form.querySelector("button[type='submit']");
    submitBtn.disabled = true;

    fetch("/api/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: name.value.trim(),
        email: email.value.trim(),
        password: password.value,
        confirm_password: confirm.value
      })
    })
      .then(function (response) {
        return response.json().then(function (data) {
          return { ok: response.ok, data: data };
        });
      })
      .then(function (result) {
        if (result.ok && result.data.success) {
          showToast(result.data.message, "success");
          setTimeout(function () {
            window.location.href = "profile.html";
          }, 900);
          return;
        }

        // Show server-side errors under the matching fields
        const fieldMap = {
          name: name,
          email: email,
          password: password,
          confirm_password: confirm
        };
        const errors = result.data.errors || {};
        Object.keys(errors).forEach(function (key) {
          if (fieldMap[key]) setFieldError(fieldMap[key].closest(".field"), errors[key]);
        });
        showToast(result.data.message || "Registration failed.", "error");
        submitBtn.disabled = false;
      })
      .catch(function () {
        showToast("Could not reach the server. Is Flask running?", "error");
        submitBtn.disabled = false;
      });
  });
}

/* ---------------------------------------------------------
   Login form
   --------------------------------------------------------- */
function initLoginForm() {
  const form = document.getElementById("login-form");
  if (!form) return;

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    clearAllErrors(form);
    let valid = true;

    const email = form.querySelector("#login-email");
    const password = form.querySelector("#login-password");

    if (!email.value.trim()) {
      setFieldError(email.closest(".field"), "Please enter your NITER email.");
      valid = false;
    }
    if (!password.value.trim()) {
      setFieldError(password.closest(".field"), "Please enter your password.");
      valid = false;
    }

    if (!valid) return;

    // Send the login details to the Flask backend
    const submitBtn = form.querySelector("button[type='submit']");
    submitBtn.disabled = true;

    fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: email.value.trim(),
        password: password.value
      })
    })
      .then(function (response) {
        return response.json().then(function (data) {
          return { ok: response.ok, data: data };
        });
      })
      .then(function (result) {
        if (result.ok && result.data.success) {
          showToast(result.data.message, "success");
          setTimeout(function () {
            window.location.href = "preferences.html";
          }, 800);
          return;
        }

        const errors = result.data.errors || {};
        if (errors.email) setFieldError(email.closest(".field"), errors.email);
        if (errors.password) setFieldError(password.closest(".field"), errors.password);
        showToast(result.data.message || "Login failed.", "error");
        submitBtn.disabled = false;
      })
      .catch(function () {
        showToast("Could not reach the server. Is Flask running?", "error");
        submitBtn.disabled = false;
      });
  });
}

/* ---------------------------------------------------------
   Navbar login state + Logout
   On every page, ask the server "who is logged in?" (/api/me).
   If someone is, replace the Login / Get Started buttons with
   their name and a Log out button. If not, leave the navbar as is.
   --------------------------------------------------------- */
function initAuthNav() {
  const actions = document.querySelector(".nav-actions");
  if (!actions) return;

  fetch("/api/me")
    .then(function (response) {
      if (!response.ok) return null;   // 401 = not logged in
      return response.json();
    })
    .then(function (data) {
      if (!data || !data.success) return;

      const greeting = document.createElement("span");
      greeting.textContent = "Hi, " + data.user.name.split(" ")[0];
      greeting.style.marginRight = "12px";
      greeting.style.fontWeight = "500";

      const logoutBtn = document.createElement("button");
      logoutBtn.type = "button";
      logoutBtn.className = "btn btn-secondary";
      logoutBtn.textContent = "Log out";
      logoutBtn.addEventListener("click", handleLogout);

      actions.innerHTML = "";
      actions.appendChild(greeting);
      actions.appendChild(logoutBtn);

      // Logged-in students also get a link to the requests page.
      const navLinks = document.querySelector(".nav-links");
      if (navLinks && !navLinks.querySelector('a[href="requests.html"]')) {
        const requestsLink = document.createElement("a");
        requestsLink.href = "requests.html";
        requestsLink.textContent = "Requests";
        navLinks.appendChild(requestsLink);
      }
    })
    .catch(function () {
      // Server not reachable: just keep the normal navbar.
    });
}

function handleLogout() {
  fetch("/api/logout", { method: "POST" })
    .then(function () {
      showToast("You have been logged out.", "success");
      setTimeout(function () {
        window.location.href = "index.html";
      }, 600);
    })
    .catch(function () {
      showToast("Could not log out. Is Flask running?", "error");
    });
}

/* ---------------------------------------------------------
   Profile setup form
   --------------------------------------------------------- */
/* Small helper for talking to the Flask API.
   Resolves to { status, ok, data } and never throws on HTTP errors. */
function apiRequest(method, url, body) {
  const options = { method: method, headers: {} };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  return fetch(url, options).then(function (response) {
    return response.json().catch(function () { return {}; }).then(function (data) {
      return { status: response.status, ok: response.ok, data: data };
    });
  });
}

function redirectToLogin() {
  showToast("Please log in to continue.", "error");
  setTimeout(function () {
    window.location.href = "login.html";
  }, 900);
}

function firstErrorMessage(errors, fallback) {
  const keys = Object.keys(errors || {});
  return keys.length ? errors[keys[0]] : fallback;
}

function initProfileForm() {
  const form = document.getElementById("profile-form");
  if (!form) return;

  // form field id  ->  API field name
  const fieldMap = {
    "p-full-name": "full_name",
    "p-department": "department",
    "p-year": "year",
    "p-gender": "gender",
    "p-area": "area",
    "p-budget": "budget",
    "p-about": "about"
  };

  // 1) Load the saved profile (the server decides whose profile: the logged-in user's)
  apiRequest("GET", "/api/profile")
    .then(function (res) {
      if (res.status === 401) { redirectToLogin(); return; }
      if (!res.ok || !res.data.profile) {
        showToast("Could not load your profile.", "error");
        return;
      }
      Object.keys(fieldMap).forEach(function (id) {
        const value = res.data.profile[fieldMap[id]];
        if (value !== null && value !== undefined) {
          document.getElementById(id).value = value;
        }
      });
    })
    .catch(function () {
      showToast("Could not reach the server. Is Flask running?", "error");
    });

  // 2) Save
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    clearAllErrors(form);
    let valid = true;

    const required = form.querySelectorAll("[data-required='true']");
    required.forEach(function (input) {
      if (!input.value.trim()) {
        setFieldError(input.closest(".field"), "This field is required.");
        valid = false;
      }
    });

    if (!valid) return;

    const payload = {};
    Object.keys(fieldMap).forEach(function (id) {
      payload[fieldMap[id]] = document.getElementById(id).value;
    });
    payload.budget = Number(payload.budget);

    const submitBtn = form.querySelector("button[type='submit']");
    submitBtn.disabled = true;

    apiRequest("PUT", "/api/profile", payload)
      .then(function (res) {
        if (res.status === 401) { redirectToLogin(); return; }
        if (res.ok && res.data.success) {
          showToast(res.data.message, "success");
          setTimeout(function () {
            window.location.href = "preferences.html";
          }, 800);
          return;
        }

        // Show server-side errors under the matching fields
        const errors = res.data.errors || {};
        Object.keys(fieldMap).forEach(function (id) {
          if (errors[fieldMap[id]]) {
            setFieldError(document.getElementById(id).closest(".field"), errors[fieldMap[id]]);
          }
        });
        showToast(res.data.message || "Could not save your profile.", "error");
        submitBtn.disabled = false;
      })
      .catch(function () {
        showToast("Could not reach the server. Is Flask running?", "error");
        submitBtn.disabled = false;
      });
  });
}

/* ---------------------------------------------------------
   Preferences form (private roommate preferences)
   --------------------------------------------------------- */
function initPreferencesForm() {
  const form = document.getElementById("preferences-form");
  if (!form) return;

  // radio group name in the HTML  ->  API field name
  const radioMap = {
    "gender-pref": "gender",
    "roommate-gender-pref": "preferred_roommate_gender",
    "sleep-schedule": "sleep_schedule",
    "cooking-pref": "cooking_preference",
    "expense-pref": "expense_preference",
    "guest-pref": "guest_preference",
    "pet-pref": "pet_preference"
  };
  const radioLabels = {
    "gender-pref": "your gender",
    "roommate-gender-pref": "the gender of roommate you prefer",
    "sleep-schedule": "your sleeping schedule",
    "cooking-pref": "your cooking preference",
    "expense-pref": "your shared-expenses preference",
    "guest-pref": "your guest preference",
    "pet-pref": "your pet preference"
  };

  function checkedValue(name) {
    const el = form.querySelector('input[name="' + name + '"]:checked');
    return el ? el.value : null;
  }

  function fillForm(p) {
    Object.keys(radioMap).forEach(function (name) {
      form.querySelectorAll('input[name="' + name + '"]').forEach(function (r) {
        r.checked = (r.value === p[radioMap[name]]);
      });
    });
    form.querySelectorAll('input[name="lifestyle"]').forEach(function (c) {
      c.checked = (p.lifestyle_qualities || []).indexOf(c.value) !== -1;
    });
    document.getElementById("pref-location").value = p.preferred_area;
    document.getElementById("budget-min").value = p.min_budget;
    document.getElementById("budget-max").value = p.max_budget;
  }

  // 1) Load saved preferences (always the logged-in user's own)
  apiRequest("GET", "/api/preferences")
    .then(function (res) {
      if (res.status === 401) { redirectToLogin(); return; }
      if (!res.ok) {
        showToast("Could not load your preferences.", "error");
        return;
      }
      if (res.data.has_preferences && res.data.preferences) {
        fillForm(res.data.preferences);
      }
    })
    .catch(function () {
      showToast("Could not reach the server. Is Flask running?", "error");
    });

  // 2) Save
  form.addEventListener("submit", function (e) {
    e.preventDefault();

    const payload = {};
    for (const name in radioMap) {
      const value = checkedValue(name);
      if (value === null) {
        showToast("Please choose " + radioLabels[name] + ".", "error");
        return;
      }
      payload[radioMap[name]] = value;
    }

    payload.preferred_area = document.getElementById("pref-location").value;
    payload.lifestyle_qualities = Array.prototype.map.call(
      form.querySelectorAll('input[name="lifestyle"]:checked'),
      function (c) { return c.value; }
    );

    const minText = document.getElementById("budget-min").value.trim();
    const maxText = document.getElementById("budget-max").value.trim();
    payload.min_budget = minText === "" ? null : Number(minText);
    payload.max_budget = maxText === "" ? null : Number(maxText);

    // Friendly checks (the server checks everything again)
    if (payload.lifestyle_qualities.length === 0) {
      showToast("Please select at least one roommate quality.", "error");
      return;
    }
    if (payload.min_budget === null || payload.max_budget === null ||
        isNaN(payload.min_budget) || isNaN(payload.max_budget)) {
      showToast("Please enter both a minimum and a maximum budget.", "error");
      return;
    }
    if (payload.min_budget < 0 || payload.max_budget < 0) {
      showToast("Budget cannot be negative.", "error");
      return;
    }
    if (payload.max_budget < payload.min_budget) {
      showToast("Maximum budget must be at least the minimum budget.", "error");
      return;
    }

    const submitBtn = form.querySelector("button[type='submit']");
    submitBtn.disabled = true;

    apiRequest("PUT", "/api/preferences", payload)
      .then(function (res) {
        if (res.status === 401) { redirectToLogin(); return; }
        if (res.ok && res.data.success) {
          showToast(res.data.message, "success");
          setTimeout(function () {
            window.location.href = "matches.html";
          }, 700);
          return;
        }
        showToast(firstErrorMessage(res.data.errors, res.data.message || "Could not save your preferences."), "error");
        submitBtn.disabled = false;
      })
      .catch(function () {
        showToast("Could not reach the server. Is Flask running?", "error");
        submitBtn.disabled = false;
      });
  });
}

/* ---------------------------------------------------------
   Roommate requests page (requests.html)
   Lists received/sent requests and lets the student send, accept,
   reject, cancel, choose what to share, and view what others shared.
   The server enforces every rule; this page only shows/hides buttons.
   --------------------------------------------------------- */
const PREF_FIELD_LABELS = {
  gender: "Gender",
  preferred_area: "Preferred area",
  min_budget: "Minimum budget",
  max_budget: "Maximum budget",
  lifestyle_qualities: "Roommate qualities",
  sleep_schedule: "Sleeping schedule",
  cooking_preference: "Cooking",
  expense_preference: "Shared expenses",
  guest_preference: "Guests",
  pet_preference: "Pets"
};
const PREF_FIELD_ORDER = Object.keys(PREF_FIELD_LABELS);
const CHECK_ICON_SVG = '<svg class="check-icon" viewBox="0 0 16 16" fill="currentColor"><path d="M13.5 4.5l-7 7-3-3 1-1 2 2 6-6z"/></svg>';

// Small helper: build an element with plain text (never innerHTML, so names cannot inject HTML)
function makeEl(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function nameInitials(name) {
  const parts = String(name || "?").trim().split(/\s+/);
  return ((parts[0] || "?")[0] + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

function formatPrefValue(key, value) {
  if (Array.isArray(value)) return value.join(", ");
  if (key === "min_budget" || key === "max_budget") return "\u09F3" + Number(value).toLocaleString("en-US");
  return String(value);
}

// A group of checkboxes, one per preference field. Returns { node, getSelected }.
function buildFieldPicker(idPrefix, selected) {
  const grid = makeEl("div", "choice-grid");
  grid.style.margin = "10px 0 14px";
  PREF_FIELD_ORDER.forEach(function (field) {
    const card = makeEl("div", "choice-card");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = field;
    input.id = idPrefix + "-" + field;
    input.checked = (selected || []).indexOf(field) !== -1;
    const label = document.createElement("label");
    label.setAttribute("for", input.id);
    label.innerHTML = CHECK_ICON_SVG;                       // fixed, trusted icon markup
    label.appendChild(document.createTextNode(PREF_FIELD_LABELS[field]));
    card.appendChild(input);
    card.appendChild(label);
    grid.appendChild(card);
  });
  return {
    node: grid,
    getSelected: function () {
      return Array.prototype.map.call(grid.querySelectorAll("input:checked"), function (i) { return i.value; });
    }
  };
}

function initRequestsPage() {
  const receivedBox = document.getElementById("rq-received");
  if (!receivedBox) return;                                  // not the requests page
  const sentBox = document.getElementById("rq-sent");
  const sharedPanel = document.getElementById("rq-shared-panel");
  const sharedBody = document.getElementById("rq-shared-body");

  function handleFailure(res, fallback) {
    if (res.status === 401) { redirectToLogin(); return; }
    showToast(res.data.message || fallback, "error");
  }

  function sendAction(method, url, body, doneMessage) {
    return apiRequest(method, url, body).then(function (res) {
      if (res.ok && res.data.success) {
        showToast(res.data.message || doneMessage, "success");
        loadRequests();
        return true;
      } else {
        handleFailure(res, "Something went wrong.");
        return false;
      }
    }).catch(function () {
      showToast("Could not reach the server. Is Flask running?", "error");
      return false;
    });
  }

  function normalizeWhatsAppInput(value) {
    const text = value.trim();
    if (!/^\+[0-9\s().-]+$/.test(text)) return null;
    const digits = text.replace(/\D/g, "");
    return digits.length >= 8 && digits.length <= 15 && digits.charAt(0) !== "0"
      ? digits
      : null;
  }

  function buildWhatsAppInput(prefix, initiallyVisible) {
    const group = makeEl("div", "whatsapp-number-field");
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "tel";
    input.id = prefix + "-number";
    input.name = "whatsapp_number";
    input.autocomplete = "tel";
    input.inputMode = "tel";
    input.placeholder = "+ country calling code and number";
    input.setAttribute("aria-describedby", prefix + "-help " + prefix + "-error");
    label.setAttribute("for", input.id);
    label.textContent = "WhatsApp number";
    const help = makeEl(
      "p", "pref-note", "Enter your number in international format, including its country calling code."
    );
    help.id = prefix + "-help";
    const error = makeEl("p", "field-error");
    error.id = prefix + "-error";
    error.setAttribute("role", "alert");
    error.hidden = true;
    group.appendChild(label);
    group.appendChild(input);
    group.appendChild(help);
    group.appendChild(error);
    group.hidden = !initiallyVisible;
    return { node: group, input: input, error: error };
  }

  function showSharedPreferences(userId) {
    apiRequest("GET", "/api/users/" + userId + "/shared-preferences").then(function (res) {
      if (!res.ok || !res.data.success) { handleFailure(res, "You cannot view these preferences."); return; }
      sharedBody.innerHTML = "";
      sharedBody.appendChild(makeEl("h3", "", res.data.owner.name + " shared these preferences with you"));
      if (!res.data.has_preferences) {
        sharedBody.appendChild(makeEl("p", "pref-note", "They have not saved any preferences yet."));
      } else {
        const list = makeEl("ul", "match-facts");
        res.data.shared_fields.forEach(function (field) {
          const li = makeEl("li");
          li.appendChild(makeEl("strong", "", PREF_FIELD_LABELS[field] + ": "));
          li.appendChild(document.createTextNode(formatPrefValue(field, res.data.preferences[field])));
          list.appendChild(li);
        });
        sharedBody.appendChild(list);
      }
      sharedPanel.style.display = "block";
      sharedPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    }).catch(function () {
      showToast("Could not reach the server. Is Flask running?", "error");
    });
  }

  function renderCard(r) {
    const card = makeEl("div", "match-card");

    const top = makeEl("div", "match-card-top");
    const identity = makeEl("div", "match-identity");
    identity.appendChild(makeEl("div", "avatar", nameInitials(r.other_user.name)));
    const info = makeEl("div");
    info.appendChild(makeEl("h3", "", r.other_user.name));
    const when = r.created_at ? r.created_at.slice(0, 10) : "";
    info.appendChild(makeEl("div", "match-meta", "Student ID " + r.other_user.id + " \u00B7 " + when));
    identity.appendChild(info);
    top.appendChild(identity);
    const status = makeEl("span", "tag", r.status.charAt(0).toUpperCase() + r.status.slice(1));
    status.setAttribute("role", "status");
    status.setAttribute("aria-label", "Request status: " + r.status);
    top.appendChild(status);
    card.appendChild(top);

    const actions = makeEl("div");
    actions.style.marginTop = "16px";

    if (r.status === "pending" && r.direction === "received") {
      actions.appendChild(makeEl("p", "pref-note", "Choose which of your preferences " + r.other_user.name + " may see if you accept (you can pick none and change this later)."));
      const picker = buildFieldPicker("accept-" + r.id, []);
      actions.appendChild(picker.node);

      const consent = makeEl("div", "whatsapp-consent");
      const consentInput = document.createElement("input");
      consentInput.type = "checkbox";
      consentInput.id = "accept-whatsapp-" + r.id;
      const consentLabel = document.createElement("label");
      consentLabel.setAttribute("for", consentInput.id);
      consentLabel.textContent =
        "Share my WhatsApp number with this student so we can communicate.";
      consent.appendChild(makeEl(
        "p", "pref-note", "This is optional. You can accept without sharing, and can withdraw sharing later."
      ));
      const numberInput = buildWhatsAppInput("accept-whatsapp-" + r.id, false);
      consentInput.addEventListener("change", function () {
        numberInput.node.hidden = !consentInput.checked;
        if (!consentInput.checked) {
          numberInput.input.value = "";
          numberInput.error.textContent = "";
          numberInput.error.hidden = true;
          numberInput.input.removeAttribute("aria-invalid");
        }
      });
      consent.appendChild(consentInput);
      consent.appendChild(consentLabel);
      consent.appendChild(numberInput.node);
      actions.appendChild(consent);

      const acceptBtn = makeEl("button", "btn btn-primary", "Accept");
      acceptBtn.type = "button";
      const rejectBtn = makeEl("button", "btn btn-secondary", "Reject");
      rejectBtn.type = "button";
      rejectBtn.style.marginLeft = "10px";
      acceptBtn.addEventListener("click", function () {
        const body = { share_fields: picker.getSelected(), share_whatsapp: consentInput.checked };
        if (consentInput.checked) {
          const normalized = normalizeWhatsAppInput(numberInput.input.value);
          if (!normalized) {
            numberInput.error.textContent =
              "Enter a valid international number with its country calling code.";
            numberInput.error.hidden = false;
            numberInput.input.setAttribute("aria-invalid", "true");
            numberInput.input.focus();
            return;
          }
          numberInput.error.textContent = "";
          numberInput.error.hidden = true;
          numberInput.input.removeAttribute("aria-invalid");
          body.phone_number = "+" + normalized;
        }
        acceptBtn.disabled = true;
        rejectBtn.disabled = true;
        sendAction("PUT", "/api/requests/" + r.id + "/accept", body, "Request accepted.")
          .then(function (ok) {
            if (!ok) {
              acceptBtn.disabled = false;
              rejectBtn.disabled = false;
            }
          });
      });
      rejectBtn.addEventListener("click", function () {
        rejectBtn.disabled = true;
        acceptBtn.disabled = true;
        sendAction("PUT", "/api/requests/" + r.id + "/reject", {}, "Request rejected.")
          .then(function (ok) {
            if (!ok) {
              acceptBtn.disabled = false;
              rejectBtn.disabled = false;
            }
          });
      });
      actions.appendChild(acceptBtn);
      actions.appendChild(rejectBtn);
    } else if (r.status === "pending" && r.direction === "sent") {
      actions.appendChild(makeEl("p", "pref-note", "Waiting for " + r.other_user.name + " to answer."));
      const cancelBtn = makeEl("button", "btn btn-secondary", "Cancel request");
      cancelBtn.type = "button";
      cancelBtn.addEventListener("click", function () {
        cancelBtn.disabled = true;
        sendAction("PUT", "/api/requests/" + r.id + "/cancel", {}, "Request cancelled.");
      });
      actions.appendChild(cancelBtn);
    } else if (r.status === "accepted") {
      actions.appendChild(makeEl("p", "pref-note", "Preferences I share with " + r.other_user.name + " (untick everything to stop sharing):"));
      const picker = buildFieldPicker("share-" + r.id, r.i_share);
      actions.appendChild(picker.node);
      const saveBtn = makeEl("button", "btn btn-primary", "Save sharing");
      saveBtn.type = "button";
      saveBtn.addEventListener("click", function () {
        saveBtn.disabled = true;
        sendAction("PUT", "/api/requests/" + r.id + "/sharing", { fields: picker.getSelected() }, "Sharing updated.");
      });
      actions.appendChild(saveBtn);

      if (r.they_share) {
        const viewBtn = makeEl("button", "btn btn-accent", "View their shared preferences");
        viewBtn.type = "button";
        viewBtn.style.marginLeft = "10px";
        viewBtn.addEventListener("click", function () { showSharedPreferences(r.other_user.id); });
        actions.appendChild(viewBtn);
      } else {
        actions.appendChild(makeEl("p", "pref-note", r.other_user.name + " has not shared any preferences with you."));
      }

      const contactSection = makeEl("div", "whatsapp-section");
      contactSection.appendChild(makeEl("h4", "", "WhatsApp contact"));
      if (r.i_share_whatsapp) {
        contactSection.appendChild(makeEl(
          "p", "pref-note", "You have shared your WhatsApp number with " + r.other_user.name + "."
        ));
        const revokeButton = makeEl("button", "btn btn-secondary", "Stop sharing WhatsApp number");
        revokeButton.type = "button";
        revokeButton.addEventListener("click", function () {
          revokeButton.disabled = true;
          sendAction("PUT", "/api/requests/" + r.id + "/whatsapp", { share: false },
            "WhatsApp sharing withdrawn.").then(function (ok) {
              if (!ok) revokeButton.disabled = false;
            });
        });
        contactSection.appendChild(revokeButton);
      } else {
        contactSection.appendChild(makeEl(
          "p", "pref-note", "Your WhatsApp number has not been shared with this student."
        ));
        const ownConsent = document.createElement("input");
        ownConsent.type = "checkbox";
        ownConsent.id = "share-whatsapp-" + r.id;
        const ownLabel = document.createElement("label");
        ownLabel.setAttribute("for", ownConsent.id);
        ownLabel.textContent =
          "Share my WhatsApp number with this student so we can communicate.";
        const ownNumber = buildWhatsAppInput("share-whatsapp-" + r.id, false);
        ownConsent.addEventListener("change", function () {
          ownNumber.node.hidden = !ownConsent.checked;
          if (!ownConsent.checked) {
            ownNumber.input.value = "";
            ownNumber.error.textContent = "";
            ownNumber.error.hidden = true;
            ownNumber.input.removeAttribute("aria-invalid");
          }
        });
        contactSection.appendChild(ownConsent);
        contactSection.appendChild(ownLabel);
        contactSection.appendChild(ownNumber.node);
        const shareButton = makeEl("button", "btn btn-primary", "Save WhatsApp sharing");
        shareButton.type = "button";
        shareButton.addEventListener("click", function () {
          if (!ownConsent.checked) {
            ownNumber.error.textContent = "Select the consent checkbox before sharing your number.";
            ownNumber.error.hidden = false;
            ownConsent.focus();
            return;
          }
          const normalized = normalizeWhatsAppInput(ownNumber.input.value);
          if (!normalized) {
            ownNumber.error.textContent =
              "Enter a valid international number with its country calling code.";
            ownNumber.error.hidden = false;
            ownNumber.input.setAttribute("aria-invalid", "true");
            ownNumber.input.focus();
            return;
          }
          ownNumber.error.textContent = "";
          ownNumber.error.hidden = true;
          ownNumber.input.removeAttribute("aria-invalid");
          shareButton.disabled = true;
          sendAction("PUT", "/api/requests/" + r.id + "/whatsapp", {
            share: true, phone_number: "+" + normalized,
          }, "WhatsApp sharing saved.").then(function (ok) {
            if (!ok) shareButton.disabled = false;
          });
        });
        contactSection.appendChild(shareButton);
      }

      if (r.they_share_whatsapp) {
        const viewContactButton = makeEl("button", "btn btn-accent", "Show shared WhatsApp contact");
        viewContactButton.type = "button";
        const contactOutput = makeEl("div", "whatsapp-contact");
        contactOutput.setAttribute("aria-live", "polite");
        viewContactButton.addEventListener("click", function () {
          viewContactButton.disabled = true;
          apiRequest("GET", "/api/requests/" + r.id + "/whatsapp").then(function (res) {
            viewContactButton.disabled = false;
            contactOutput.textContent = "";
            if (res.status === 401) { redirectToLogin(); return; }
            if (!res.ok || !res.data.success) {
              handleFailure(res, "Could not load the shared WhatsApp contact.");
              return;
            }
            if (!res.data.shared) {
              contactOutput.appendChild(makeEl(
                "p", "pref-note", r.other_user.name + " has not shared their WhatsApp number."
              ));
              return;
            }
            if (typeof res.data.phone_number !== "string" ||
                !/^[1-9][0-9]{7,14}$/.test(res.data.phone_number)) {
              showToast("The shared WhatsApp contact could not be displayed.", "error");
              return;
            }
            contactOutput.appendChild(makeEl("p", "", "WhatsApp number: " + res.data.phone_number));
            const chatLink = makeEl("a", "btn btn-accent", "Chat on WhatsApp");
            chatLink.href = "https://wa.me/" + res.data.phone_number;
            chatLink.target = "_blank";
            chatLink.rel = "noopener noreferrer";
            contactOutput.appendChild(chatLink);
          }).catch(function () {
            viewContactButton.disabled = false;
            showToast("Could not reach the server. Is Flask running?", "error");
          });
        });
        contactSection.appendChild(viewContactButton);
        contactSection.appendChild(contactOutput);
      } else {
        contactSection.appendChild(makeEl(
          "p", "pref-note", r.other_user.name + " has not shared their WhatsApp number."
        ));
      }
      actions.appendChild(contactSection);
    }
    card.appendChild(actions);
    return card;
  }

  function renderList(box, requests, emptyText) {
    box.innerHTML = "";
    if (!requests.length) {
      box.style.display = "block";
      box.appendChild(makeEl("p", "pref-note", emptyText));
      return;
    }
    box.style.display = "";
    requests.forEach(function (r) { box.appendChild(renderCard(r)); });
  }

  function loadRequests() {
    // Hide the shared-preferences panel: a refresh must never leave stale permission on screen.
    sharedPanel.style.display = "none";
    Promise.all([apiRequest("GET", "/api/requests/received"), apiRequest("GET", "/api/requests/sent")])
      .then(function (results) {
        if (results[0].status === 401 || results[1].status === 401) { redirectToLogin(); return; }
        if (!results[0].ok || !results[1].ok) { showToast("Could not load your requests.", "error"); return; }
        renderList(receivedBox, results[0].data.requests, "No requests received yet.");
        renderList(sentBox, results[1].data.requests, "You have not sent any requests yet.");
      })
      .catch(function () {
        showToast("Could not reach the server. Is Flask running?", "error");
      });
  }

  // Show my own student ID (needed by the temporary test tool)
  apiRequest("GET", "/api/me").then(function (res) {
    if (res.status === 401) { redirectToLogin(); return; }
    if (res.ok && res.data.user) {
      document.getElementById("rq-my-id").textContent = res.data.user.id;
    }
  }).catch(function () {});

  // Manual student-ID request entry remains available alongside match-based requests.
  const sendBtn = document.getElementById("rq-send-btn");
  const idInput = document.getElementById("rq-receiver-id");
  sendBtn.addEventListener("click", function () {
    const field = idInput.closest(".field");
    clearFieldError(field);
    const text = idInput.value.trim();
    const id = Number(text);
    if (text === "" || !Number.isInteger(id) || id < 1) {
      setFieldError(field, "Enter a student ID (a whole number, 1 or higher).");
      return;
    }
    sendBtn.disabled = true;
    apiRequest("POST", "/api/requests", { receiver_id: id }).then(function (res) {
      sendBtn.disabled = false;
      if (res.ok && res.data.success) {
        showToast(res.data.message, "success");
        idInput.value = "";
        loadRequests();
      } else {
        handleFailure(res, "Could not send the request.");
      }
    }).catch(function () {
      sendBtn.disabled = false;
      showToast("Could not reach the server. Is Flask running?", "error");
    });
  });

  loadRequests();
}

/* ---------------------------------------------------------
   Matches page filters
   Cards carry data-location, data-budget and data-compat
   attributes in the HTML; this just shows/hides them.
   --------------------------------------------------------- */
function initMatchFilters() {
  const locationSelect = document.getElementById("filter-location");
  const budgetSelect = document.getElementById("filter-budget");
  const compatSelect = document.getElementById("filter-compat");
  const cards = document.querySelectorAll(".match-card");
  const countLabel = document.querySelector(".filter-count");

  if (!cards.length || (!locationSelect && !budgetSelect && !compatSelect)) return;

  function applyFilters() {
    const location = locationSelect ? locationSelect.value : "all";
    const budget = budgetSelect ? budgetSelect.value : "all";
    const compat = compatSelect ? compatSelect.value : "all";
    let visible = 0;

    cards.forEach(function (card) {
      const cardLocation = card.getAttribute("data-location");
      const cardBudgetMax = parseInt(card.getAttribute("data-budget-max"), 10);
      const cardCompat = parseInt(card.getAttribute("data-compat"), 10);

      let show = true;

      if (location !== "all" && cardLocation !== location) show = false;

      if (budget === "under4000" && cardBudgetMax >= 4000) show = false;
      if (budget === "4000to5000" && (cardBudgetMax < 4000 || cardBudgetMax > 5000)) show = false;
      if (budget === "over5000" && cardBudgetMax <= 5000) show = false;

      if (compat === "90" && cardCompat < 90) show = false;
      if (compat === "80" && cardCompat < 80) show = false;
      if (compat === "70" && cardCompat < 70) show = false;

      card.style.display = show ? "" : "none";
      if (show) visible++;
    });

    if (countLabel) {
      countLabel.textContent = visible + (visible === 1 ? " match shown" : " matches shown");
    }
  }

  [locationSelect, budgetSelect, compatSelect].forEach(function (select) {
    if (select) select.addEventListener("change", applyFilters);
  });

  applyFilters();
}

/* ---------------------------------------------------------
   Matches page (matches.html): real recommendations
   Fetches GET /api/matches (the logged-in student, taken from the
   Flask session) and draws one card per recommendation.
   It shows ONLY what that API returns: first name, department, year,
   a coarse band, reasons and request status. All text is inserted with
   textContent (never innerHTML), so nothing from the server can inject HTML.
   --------------------------------------------------------- */
const MATCH_BANDS = ["Strong", "Good", "Fair"];
const MATCH_STATUSES = ["ok", "no_matches", "needs_profile", "needs_preferences",
                        "needs_roommate_gender", "invalid_preferences"];

function initMatchesPage() {
  const root = document.getElementById("matches-root");
  if (!root) return;

  const notice = document.getElementById("matches-notice");
  const stateBox = document.getElementById("matches-state");
  const results = document.getElementById("matches-results");
  const grid = document.getElementById("match-grid");
  const countEl = document.getElementById("match-count");
  const countLabel = document.getElementById("match-count-label");
  const filterSelect = document.getElementById("filter-band");
  const filterCount = document.getElementById("filter-count");
  const filterEmpty = document.getElementById("filter-empty");
  if (!notice || !stateBox || !results || !grid || !countEl || !countLabel ||
      !filterSelect || !filterCount || !filterEmpty) return;

  let isLoading = false;   // stops a second request while one is already running

  // ---- state boxes -------------------------------------------------
  function clearState() { stateBox.textContent = ""; }

  function showState(kind, title, message, actions) {
    clearState();
    results.hidden = true;
    stateBox.setAttribute("aria-busy", String(kind === "loading"));
    const box = makeEl("div", "state-box" + (kind === "error" ? " state-error" : ""));
    box.setAttribute("role", kind === "error" ? "alert" : "status");
    if (kind === "loading") {
      const spinner = makeEl("div", "spinner");
      spinner.setAttribute("aria-hidden", "true");
      box.appendChild(spinner);
    }
    box.appendChild(makeEl("h3", "", title));
    if (message) box.appendChild(makeEl("p", "", message));
    if (actions && actions.length) {
      const row = makeEl("div", "state-actions");
      actions.forEach(function (a) {
        if (a.href) {
          const link = makeEl("a", "btn " + (a.secondary ? "btn-secondary" : "btn-primary"), a.text);
          link.href = a.href;
          row.appendChild(link);
        } else {
          const btn = makeEl("button", "btn " + (a.secondary ? "btn-secondary" : "btn-primary"), a.text);
          btn.type = "button";
          btn.addEventListener("click", a.onClick);
          row.appendChild(btn);
        }
      });
      box.appendChild(row);
    }
    stateBox.appendChild(box);
  }

  function showError(message) {
    notice.hidden = true;
    showState("error", "We could not load your matches", message,
              [{ text: "Try again", onClick: loadMatches }]);
  }

  // ---- checking the API data before drawing it ----------------------
  function textList(value) {
    if (!Array.isArray(value)) return [];
    return value.filter(function (x) { return typeof x === "string" && x.trim() !== ""; });
  }

  // Returns a clean card object, or null if this entry is not usable.
  function cleanMatch(raw) {
    if (!raw || typeof raw !== "object") return null;
    if (!Number.isInteger(raw.user_id) || raw.user_id <= 0) return null;
    if (typeof raw.first_name !== "string" || raw.first_name.trim() === "") return null;
    if (MATCH_BANDS.indexOf(raw.compatibility_band) === -1) return null;

    let request = null;
    if (raw.request && typeof raw.request === "object" &&
        typeof raw.request.status === "string" &&
        (raw.request.direction === "sent" || raw.request.direction === "received")) {
      request = { status: raw.request.status, direction: raw.request.direction };
    }
    return {
      id: raw.user_id,
      firstName: raw.first_name.trim(),
      department: typeof raw.department === "string" ? raw.department.trim() : "",
      year: typeof raw.year === "string" ? raw.year.trim() : "",
      band: raw.compatibility_band,
      reasons: textList(raw.reasons),
      differences: textList(raw.differences),
      canViewShared: raw.can_view_shared_preferences === true,
      request: request
    };
  }

  function requestNote(request) {
    if (!request) return "";
    if (request.status === "pending" && request.direction === "sent") return "Roommate request sent. Waiting for a reply.";
    if (request.status === "pending" && request.direction === "received") return "This student sent you a roommate request.";
    if (request.status === "accepted") return "Roommate request accepted.";
    return "";
  }

  // ---- drawing ------------------------------------------------------
  function buildCard(m) {
    const card = makeEl("div", "match-card" + (m.band === "Strong" ? "" : " compat-med"));
    card.setAttribute("data-band", m.band);

    const top = makeEl("div", "match-card-top");
    const identity = makeEl("div", "match-identity");
    identity.appendChild(makeEl("div", "avatar", nameInitials(m.firstName)));
    const who = makeEl("div");
    who.appendChild(makeEl("h3", "", m.firstName));
    const meta = [m.department, m.year].filter(function (x) { return x !== ""; }).join(" \u2022 ");
    who.appendChild(makeEl("div", "match-meta", meta || "NITER student"));
    identity.appendChild(who);
    top.appendChild(identity);

    const badge = makeEl("div", "compat-badge");
    badge.appendChild(makeEl("div", "compat-num", m.band));
    badge.appendChild(makeEl("div", "compat-label", "Estimated match"));
    top.appendChild(badge);
    card.appendChild(top);

    const facts = makeEl("ul", "match-facts");
    m.reasons.forEach(function (text) {
      const li = makeEl("li");
      li.appendChild(makeEl("span", "fact-yes", "\u2713"));
      li.appendChild(document.createTextNode(" " + text));
      facts.appendChild(li);
    });
    m.differences.forEach(function (text) {
      const li = makeEl("li");
      li.appendChild(makeEl("span", "fact-partial", "~"));
      li.appendChild(document.createTextNode(" " + text));
      facts.appendChild(li);
    });
    card.appendChild(facts);

    const notes = [requestNote(m.request)];
    if (m.canViewShared) notes.push("This student has shared some preferences with you.");
    notes.filter(function (t) { return t !== ""; }).forEach(function (t) {
      card.appendChild(makeEl("p", "match-note", t));
    });

    // Real user id, same ?id= convention the profile page already reads.
    const link = makeEl("a", "btn btn-primary btn-block", "View Profile");
    link.href = "match-profile.html?id=" + encodeURIComponent(String(m.id));
    card.appendChild(link);
    return card;
  }

  function applyBandFilter() {
    const wanted = filterSelect.value;
    let visible = 0;
    grid.querySelectorAll(".match-card").forEach(function (card) {
      const show = wanted === "all" || card.getAttribute("data-band") === wanted;
      card.style.display = show ? "" : "none";
      if (show) visible++;
    });
    filterCount.textContent = visible + (visible === 1 ? " match shown" : " matches shown");
    filterEmpty.hidden = visible !== 0;
  }

  function showMatches(cards, disclaimer) {
    clearState();
    grid.textContent = "";
    const fragment = document.createDocumentFragment();
    cards.forEach(function (m) { fragment.appendChild(buildCard(m)); });
    grid.appendChild(fragment);

    countEl.textContent = String(cards.length);
    countLabel.textContent = cards.length === 1 ? "potential match found" : "potential matches found";
    filterSelect.value = "all";
    notice.textContent = typeof disclaimer === "string" ? disclaimer : "";
    notice.hidden = notice.textContent === "";
    results.hidden = false;
    applyBandFilter();
  }

  // ---- reading the response -----------------------------------------
  const SETUP_TEXT = {
    needs_profile: ["Complete your profile first", "Please complete your profile to see roommate matches.",
                    "profile.html", "Go to my profile"],
    needs_preferences: ["Save your preferences first", "Please save your roommate preferences to see matches.",
                        "preferences.html", "Go to my preferences"],
    needs_roommate_gender: ["One more question", "Please choose which gender of roommate you prefer and save your preferences again.",
                            "preferences.html", "Update my preferences"],
    invalid_preferences: ["Please review your preferences", "Some of your saved preferences are incomplete. Please review and save them again.",
                          "preferences.html", "Update my preferences"]
  };

  function handleData(data) {
    if (!data || typeof data !== "object" || data.success !== true ||
        typeof data.status !== "string" || MATCH_STATUSES.indexOf(data.status) === -1) {
      showError("The server sent an unexpected answer. Please try again in a moment.");
      return;
    }

    if (SETUP_TEXT[data.status]) {
      const t = SETUP_TEXT[data.status];
      notice.hidden = true;
      showState("info", t[0], t[1], [{ text: t[3], href: t[2] }]);
      return;
    }

    let rawList = data.matches;
    if (data.status === "no_matches") rawList = [];
    if (!Array.isArray(rawList)) {
      showError("The server sent an unexpected answer. Please try again in a moment.");
      return;
    }

    const cards = rawList.map(cleanMatch).filter(function (c) { return c !== null; });
    if (rawList.length > 0 && cards.length === 0) {
      showError("The server sent matches in an unexpected format. Please try again in a moment.");
      return;
    }

    if (cards.length === 0) {
      notice.hidden = true;
      showState("info", "No matches yet",
                "No students match your essential requirements right now. Check back later as more students join, or review your preferences.",
                [{ text: "Review my preferences", href: "preferences.html", secondary: true }]);
      return;
    }

    showMatches(cards, data.disclaimer);
  }

  function loadMatches() {
    if (isLoading) return;          // ignore double clicks and repeat calls
    isLoading = true;
    notice.hidden = true;
    showState("loading", "Finding your matches\u2026", "", null);

    apiRequest("GET", "/api/matches")
      .then(function (res) {
        isLoading = false;
        if (res.status === 401) {
          notice.hidden = true;
          showState("info", "Please log in", "Log in to see your roommate matches.",
                    [{ text: "Log in", href: "login.html" }]);
          return;
        }
        if (!res.ok) {
          showError("Something went wrong on the server. Please try again.");
          return;
        }
        handleData(res.data);
      })
      .catch(function () {
        isLoading = false;
        showError("Could not reach the server. Is Flask running?");
      });
  }

  filterSelect.addEventListener("change", applyBandFilter);   // attached once
  loadMatches();
}

/* ---------------------------------------------------------
   Match profile page (GET /api/matches/<id>)
   Only the match API's privacy-filtered fields are rendered here.
   --------------------------------------------------------- */
function initMatchProfilePage() {
  const root = document.getElementById("match-profile-root");
  if (!root) return;

  const state = document.getElementById("match-profile-state");
  const content = document.getElementById("match-profile-content");
  const feedback = document.getElementById("match-profile-feedback");
  const sendBtn = document.getElementById("send-request-btn");

  if (!state || !content || !feedback || !sendBtn) return;

  function showState(kind, title, message, linkText, href) {
    state.textContent = "";
    state.className = "state-box" + (kind === "error" ? " state-error" : "");
    state.setAttribute("role", kind === "error" ? "alert" : "status");
    state.setAttribute("aria-busy", "false");
    state.appendChild(makeEl("h2", "", title));
    if (message) state.appendChild(makeEl("p", "", message));
    if (linkText && href) {
      const link = makeEl("a", "btn btn-primary", linkText);
      link.href = href;
      state.appendChild(link);
    }
    state.hidden = false;
    content.hidden = true;
  }

  function showLoading() {
    state.textContent = "";
    state.className = "state-box";
    state.setAttribute("role", "status");
    state.setAttribute("aria-busy", "true");
    const spinner = makeEl("div", "spinner");
    spinner.setAttribute("aria-hidden", "true");
    state.appendChild(spinner);
    state.appendChild(makeEl("h2", "", "Loading match"));
    state.appendChild(makeEl("p", "", "Please wait while we check that this student is still eligible."));
    state.hidden = false;
    content.hidden = true;
  }

  function setFeedback(message, isError) {
    feedback.textContent = message || "";
    feedback.className = isError ? "match-profile-feedback error" : "match-profile-feedback";
    feedback.setAttribute("role", isError ? "alert" : "status");
  }

  function validateMatch(raw, requestedId) {
    if (!raw || typeof raw !== "object" ||
        !Number.isSafeInteger(raw.user_id) || raw.user_id !== requestedId ||
        typeof raw.first_name !== "string" || raw.first_name.trim() === "" ||
        !["Strong", "Good", "Fair"].includes(raw.compatibility_band) ||
        !Array.isArray(raw.reasons) || !Array.isArray(raw.differences)) {
      return null;
    }
    if (raw.department !== null && typeof raw.department !== "string") return null;
    if (raw.year !== null && typeof raw.year !== "string") return null;
    if (!raw.reasons.every(function (item) { return typeof item === "string"; }) ||
        !raw.differences.every(function (item) { return typeof item === "string"; })) {
      return null;
    }

    let requestState = null;
    if (raw.request !== null) {
      if (!raw.request || typeof raw.request !== "object" ||
          !["pending", "accepted"].includes(raw.request.status) ||
          !["sent", "received"].includes(raw.request.direction)) {
        return null;
      }
      requestState = { status: raw.request.status, direction: raw.request.direction };
    }
    return {
      userId: raw.user_id,
      firstName: raw.first_name.trim(),
      department: raw.department || "",
      year: raw.year || "",
      band: raw.compatibility_band,
      reasons: raw.reasons,
      differences: raw.differences,
      request: requestState
    };
  }

  function renderList(listId, items, kind) {
    const list = document.getElementById(listId);
    list.textContent = "";
    items.forEach(function (text) {
      const item = makeEl("li");
      item.appendChild(makeEl("span", kind === "reason" ? "fact-yes" : "fact-partial",
                             kind === "reason" ? "\u2713" : "~"));
      item.appendChild(document.createTextNode(" " + text));
      list.appendChild(item);
    });
    list.hidden = items.length === 0;
  }

  function renderRequestState(request) {
    sendBtn.disabled = false;
    sendBtn.textContent = "Send Roommate Request";
    sendBtn.classList.add("btn-accent");
    sendBtn.classList.remove("btn-secondary");
    if (!request) return;

    sendBtn.disabled = true;
    sendBtn.classList.remove("btn-accent");
    sendBtn.classList.add("btn-secondary");
    if (request.status === "accepted") {
      sendBtn.textContent = "Already Connected";
      setFeedback("This roommate request has been accepted.", false);
    } else if (request.direction === "sent") {
      sendBtn.textContent = "Request Sent";
      setFeedback("Your roommate request is pending.", false);
    } else {
      sendBtn.textContent = "Request Received";
      setFeedback("This student has already sent you a request. You can respond on the requests page.", false);
    }
  }

  function renderMatch(match, disclaimer) {
    document.getElementById("mp-name").textContent = match.firstName;
    document.getElementById("mp-avatar").textContent = nameInitials(match.firstName);
    document.getElementById("mp-meta").textContent =
      [match.department, match.year].filter(function (part) { return part !== ""; }).join(" \u2022 ") ||
      "NITER student";
    document.getElementById("mp-band").textContent = match.band;
    document.getElementById("match-disclaimer").textContent =
      typeof disclaimer === "string" && disclaimer.trim() ? disclaimer : "Compatibility is an estimate.";
    renderList("mp-why", match.reasons, "reason");
    renderList("mp-diff", match.differences, "difference");
    renderRequestState(match.request);
    state.hidden = true;
    content.hidden = false;
  }

  function loadMatch(requestedId, refresh) {
    if (!refresh) showLoading();
    return apiRequest("GET", "/api/matches/" + encodeURIComponent(String(requestedId)))
      .then(function (res) {
        if (res.status === 401) {
          showState("info", "Please log in", "Log in to view this roommate match.", "Log in", "login.html");
          return;
        }
        if (res.status === 404) {
          showState("info", "Match unavailable",
                    "This match is unavailable or no longer meets your requirements.",
                    "Back to matches", "matches.html");
          return;
        }
        if (!res.ok || !res.data || res.data.success !== true) {
          showState("error", "Could not load this match",
                    (res.data && typeof res.data.message === "string" && res.data.message) ||
                    "Please try again.", "Retry", "match-profile.html?id=" + encodeURIComponent(String(requestedId)));
          return;
        }
        if (res.data.status !== "ok" || !res.data.match) {
          const setupMessages = {
            needs_profile: "Complete your profile before viewing matches.",
            needs_preferences: "Save your roommate preferences before viewing matches.",
            needs_roommate_gender: "Choose your preferred roommate gender and save your preferences.",
            invalid_preferences: "Review and save your roommate preferences again.",
            no_matches: "There are no eligible matches right now."
          };
          showState("info", "Match unavailable",
                    setupMessages[res.data.status] || "This match is unavailable or no longer eligible.",
                    "Back to matches", "matches.html");
          return;
        }

        const match = validateMatch(res.data.match, requestedId);
        if (!match) {
          showState("error", "Unexpected match response",
                    "The server returned match details in an unexpected format.",
                    "Retry", "match-profile.html?id=" + encodeURIComponent(String(requestedId)));
          return;
        }
        renderMatch(match, res.data.disclaimer);
      })
      .catch(function () {
        showState("error", "Could not reach the server",
                  "Check your connection and try again.", "Retry",
                  "match-profile.html?id=" + encodeURIComponent(String(requestedId)));
      });
  }

  const idText = new URLSearchParams(window.location.search).get("id");
  if (!idText || !/^[1-9]\d*$/.test(idText)) {
    showState("info", "Invalid match link", "The match ID is missing or invalid.", "Back to matches", "matches.html");
    return;
  }
  const requestedId = Number(idText);
  if (!Number.isSafeInteger(requestedId)) {
    showState("info", "Invalid match link", "The match ID is missing or invalid.", "Back to matches", "matches.html");
    return;
  }

  sendBtn.addEventListener("click", function () {
    if (sendBtn.disabled) return;
    sendBtn.disabled = true;
    sendBtn.textContent = "Sending request\u2026";
    setFeedback("", false);
    apiRequest("POST", "/api/requests", { receiver_id: requestedId })
      .then(function (res) {
        if (res.status === 201 && res.data && res.data.success === true &&
            res.data.request && res.data.request.status === "pending" &&
            res.data.request.direction === "sent") {
          renderRequestState({ status: "pending", direction: "sent" });
          setFeedback(res.data.message || "Roommate request sent.", false);
          return;
        }
        const message = res.data && typeof res.data.message === "string" && res.data.message
          ? res.data.message : "Could not send the roommate request.";
        if (res.status === 201) {
          const unexpectedMessage = "The server returned an unexpected response. Refreshing request status.";
          setFeedback(unexpectedMessage, true);
          loadMatch(requestedId, true).then(function () { setFeedback(unexpectedMessage, true); });
          return;
        }
        setFeedback(message, true);
        if (res.status === 409) {
          loadMatch(requestedId, true).then(function () { setFeedback(message, true); });
        } else if (res.status === 401) {
          sendBtn.disabled = true;
          const login = makeEl("a", "", " Log in");
          login.href = "login.html";
          feedback.appendChild(login);
        } else {
          sendBtn.disabled = false;
          sendBtn.textContent = "Send Roommate Request";
        }
      })
      .catch(function () {
        sendBtn.disabled = false;
        sendBtn.textContent = "Send Roommate Request";
        setFeedback("Could not reach the server. Please try again.", true);
      });
  });

  loadMatch(requestedId, false);
}

/* ---------------------------------------------------------
   Toast notification system
   Call showToast("message", "success" | "error") from
   anywhere in this file.
   --------------------------------------------------------- */
function showToast(message, type) {
  let stack = document.querySelector(".toast-stack");
  if (!stack) {
    stack = document.createElement("div");
    stack.className = "toast-stack";
    stack.setAttribute("aria-live", "polite");
    stack.setAttribute("aria-relevant", "additions");
    document.body.appendChild(stack);
  }

  const toast = document.createElement("div");
  toast.className = "toast" + (type === "error" ? " toast-error" : " toast-success");
  toast.setAttribute("role", type === "error" ? "alert" : "status");
  toast.appendChild(makeEl("span", "toast-icon", type === "error" ? "\u26A0" : "\u2713"));
  toast.appendChild(makeEl("span", "", message));
  stack.appendChild(toast);

  setTimeout(function () {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.3s ease";
    setTimeout(function () { toast.remove(); }, 300);
  }, 3200);
}
