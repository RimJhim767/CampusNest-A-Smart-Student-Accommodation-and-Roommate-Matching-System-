/* =========================================================
   CampusNest — Shared JavaScript
   This file is loaded on every page. Each section checks
   that the element it needs exists before using it, so the
   same file works everywhere without throwing errors.
   ========================================================= */

/* ---------------------------------------------------------
   Dummy roommate data
   In the real app this would come from a database. For this
   prototype it's a plain JavaScript array that both the
   matches page and the match-profile page read from.
   --------------------------------------------------------- */
const CAMPUSNEST_MATCHES = [
  {
    id: "sarah-ahmed",
    name: "Sarah Ahmed",
    initials: "SA",
    dept: "CSE",
    year: "3rd Year",
    area: "Dhonia",
    budgetMin: 4500,
    budgetMax: 5500,
    compatibility: 92,
    about: "Quiet and study-focused student looking for a clean and comfortable shared living environment.",
    facts: [
      { type: "yes", text: "Budget compatible" },
      { type: "yes", text: "Location compatible" },
      { type: "yes", text: "Quiet environment" },
      { type: "yes", text: "Study-friendly" }
    ],
    why: [
      "Similar budget",
      "Same preferred location",
      "Both prefer quiet environment",
      "Both prefer study-friendly environment"
    ],
    differences: ["Different sleeping schedules"],
    prefs: ["Quiet", "Clean", "Study-friendly", "Non-smoker"]
  },
  {
    id: "nabila-rahman",
    name: "Nabila Rahman",
    initials: "NR",
    dept: "EEE",
    year: "2nd Year",
    area: "Niribili",
    budgetMin: 4000,
    budgetMax: 5000,
    compatibility: 84,
    about: "Friendly and organized, enjoys a tidy room and doesn't mind occasional guests.",
    facts: [
      { type: "yes", text: "Budget compatible" },
      { type: "yes", text: "Clean" },
      { type: "partial", text: "Lifestyle partially compatible" }
    ],
    why: [
      "Similar budget range",
      "Both prefer a clean space",
      "Both open to occasional guests"
    ],
    differences: ["Different preferred locations", "One prefers more social evenings"],
    prefs: ["Clean", "Social", "Guests welcome"]
  },
  {
    id: "tanvir-hasan",
    name: "Tanvir Hasan",
    initials: "TH",
    dept: "IPE",
    year: "4th Year",
    area: "Jalalabad",
    budgetMin: 3500,
    budgetMax: 4500,
    compatibility: 77,
    about: "Easygoing final-year student, usually out for lab work in the evenings.",
    facts: [
      { type: "yes", text: "Budget compatible" },
      { type: "partial", text: "Sleeping schedule differs" },
      { type: "yes", text: "Non-smoker" }
    ],
    why: [
      "Overlapping budget range",
      "Both non-smokers",
      "Both comfortable sharing expenses"
    ],
    differences: ["Different sleeping schedule", "Different preferred area"],
    prefs: ["Non-smoker", "Shared expenses", "Flexible schedule"]
  },
  {
    id: "farhana-islam",
    name: "Farhana Islam",
    initials: "FI",
    dept: "Textile Engineering",
    year: "1st Year",
    area: "Jalalabad",
    budgetMin: 4000,
    budgetMax: 4800,
    compatibility: 68,
    about: "New to campus, looking for a calm home base close to lectures.",
    facts: [
      { type: "yes", text: "Budget compatible" },
      { type: "partial", text: "Location partially compatible" },
      { type: "yes", text: "Quiet environment" }
    ],
    why: [
      "Similar budget",
      "Both prefer a quiet home"
    ],
    differences: ["Different preferred area", "Different year of study"],
    prefs: ["Quiet", "Study-friendly"]
  },
  {
    id: "imran-kabir",
    name: "Imran Kabir",
    initials: "IK",
    dept: "CSE",
    year: "2nd Year",
    area: "Nobinagar",
    budgetMin: 4200,
    budgetMax: 5200,
    compatibility: 88,
    about: "Balances study and hobbies well, keeps shared spaces tidy.",
    facts: [
      { type: "yes", text: "Budget compatible" },
      { type: "yes", text: "Location compatible" },
      { type: "yes", text: "Clean" }
    ],
    why: [
      "Same preferred location",
      "Similar budget",
      "Both value a clean home"
    ],
    differences: ["Different sleeping schedule"],
    prefs: ["Clean", "Study-friendly", "Pet-friendly"]
  }
];

document.addEventListener("DOMContentLoaded", function () {
  initMobileNav();
  initAuthNav();
  initPasswordToggles();
  initRegisterForm();
  initLoginForm();
  initProfileForm();
  initPreferencesForm();
  initMatchFilters();
  initMatchProfilePage();
  initSendRequestButton();
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
    "sleep-schedule": "sleep_schedule",
    "cooking-pref": "cooking_preference",
    "expense-pref": "expense_preference",
    "guest-pref": "guest_preference",
    "pet-pref": "pet_preference"
  };
  const radioLabels = {
    "gender-pref": "your gender",
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
      } else {
        handleFailure(res, "Something went wrong.");
      }
    }).catch(function () {
      showToast("Could not reach the server. Is Flask running?", "error");
    });
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
    top.appendChild(makeEl("span", "tag", r.status.charAt(0).toUpperCase() + r.status.slice(1)));
    card.appendChild(top);

    const actions = makeEl("div");
    actions.style.marginTop = "16px";

    if (r.status === "pending" && r.direction === "received") {
      actions.appendChild(makeEl("p", "pref-note", "Choose which of your preferences " + r.other_user.name + " may see if you accept (you can pick none and change this later)."));
      const picker = buildFieldPicker("accept-" + r.id, []);
      actions.appendChild(picker.node);

      const acceptBtn = makeEl("button", "btn btn-primary", "Accept");
      acceptBtn.type = "button";
      acceptBtn.addEventListener("click", function () {
        acceptBtn.disabled = true;
        sendAction("PUT", "/api/requests/" + r.id + "/accept", { share_fields: picker.getSelected() }, "Request accepted.");
      });
      const rejectBtn = makeEl("button", "btn btn-secondary", "Reject");
      rejectBtn.type = "button";
      rejectBtn.style.marginLeft = "10px";
      rejectBtn.addEventListener("click", function () {
        rejectBtn.disabled = true;
        sendAction("PUT", "/api/requests/" + r.id + "/reject", {}, "Request rejected.");
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

  // Send a request (temporary test tool until matching exists)
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
   Match profile page
   Reads ?id= from the URL and fills the page from
   CAMPUSNEST_MATCHES. Falls back to the first entry.
   --------------------------------------------------------- */
function initMatchProfilePage() {
  const root = document.getElementById("match-profile-root");
  if (!root) return;

  const params = new URLSearchParams(window.location.search);
  const id = params.get("id");
  const match = CAMPUSNEST_MATCHES.find(function (m) { return m.id === id; }) || CAMPUSNEST_MATCHES[0];

  setText("mp-name", match.name);
  setText("mp-avatar", match.initials);
  setText("mp-meta", match.dept + " \u2022 " + match.year);
  setText("mp-area", match.area);
  setText("mp-budget", "\u09F3" + match.budgetMin.toLocaleString() + "\u2013" + match.budgetMax.toLocaleString() + "/month");
  setText("mp-about", match.about);
  setText("mp-compat-num", match.compatibility + "%");

  fillList("mp-why", match.why, "yes");
  fillList("mp-diff", match.differences, "diff");
  fillTags("mp-prefs", match.prefs);
  drawCompatRing(match.compatibility);

  const sendBtn = document.getElementById("send-request-btn");
  if (sendBtn) sendBtn.setAttribute("data-name", match.name);
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function fillList(id, items, kind) {
  const el = document.getElementById(id);
  if (!el || !items) return;
  el.innerHTML = "";
  items.forEach(function (item) {
    const li = document.createElement("li");
    if (kind === "yes") {
      li.innerHTML = '<span class="fact-yes">\u2713</span> ' + item;
    } else {
      li.textContent = item;
    }
    el.appendChild(li);
  });
}

function fillTags(id, items) {
  const el = document.getElementById(id);
  if (!el || !items) return;
  el.innerHTML = "";
  items.forEach(function (item) {
    const span = document.createElement("span");
    span.className = "tag";
    span.textContent = item;
    el.appendChild(span);
  });
}

/* Draws a simple circular progress ring using SVG stroke-dasharray */
function drawCompatRing(percent) {
  const circle = document.getElementById("mp-ring-fill");
  if (!circle) return;
  const radius = circle.r.baseVal.value;
  const circumference = 2 * Math.PI * radius;
  circle.style.strokeDasharray = circumference + " " + circumference;
  circle.style.strokeDashoffset = circumference - (percent / 100) * circumference;
}

/* ---------------------------------------------------------
   Send Roommate Request button
   --------------------------------------------------------- */
function initSendRequestButton() {
  const btn = document.getElementById("send-request-btn");
  if (!btn) return;

  btn.addEventListener("click", function () {
    if (btn.disabled) return;
    const name = btn.getAttribute("data-name") || "this student";
    showToast("Roommate request sent successfully!", "success");
    btn.textContent = "Request Sent";
    btn.disabled = true;
    btn.classList.add("btn-secondary");
    btn.classList.remove("btn-accent");
  });
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
    document.body.appendChild(stack);
  }

  const toast = document.createElement("div");
  toast.className = "toast" + (type === "error" ? " toast-error" : " toast-success");
  toast.innerHTML = '<span class="toast-icon">' + (type === "error" ? "\u26A0" : "\u2713") + "</span><span>" + message + "</span>";
  stack.appendChild(toast);

  setTimeout(function () {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.3s ease";
    setTimeout(function () { toast.remove(); }, 300);
  }, 3200);
}
