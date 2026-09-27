/* The frontend shell. Views live in web/views/ and register themselves.
 *
 * Same contract as cli.py and serve.py: a view is one file that calls
 * App.view(name, render) and touches nothing else. This file is written
 * once and never rewritten, so a new view cannot break an old one.
 */
var App = (function () {
  var views = [];
  var current = null;

  function api(path, options) {
    options = options || {};
    return fetch(path, {
      method: options.method || "GET",
      headers: options.body ? { "Content-Type": "application/json" } : {},
      body: options.body ? JSON.stringify(options.body) : null
    }).then(function (r) {
      return r.text().then(function (text) {
        var data = null;
        try { data = text ? JSON.parse(text) : null; } catch (e) { data = { raw: text }; }
        if (!r.ok) {
          var msg = (data && (data.detail || data.error)) || ("HTTP " + r.status);
          throw new Error(msg);
        }
        return data;
      });
    });
  }

  function status(text, kind) {
    var el = document.getElementById("status");
    if (!el) return;
    el.textContent = text;
    el.className = kind || "";
  }

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    attrs = attrs || {};
    Object.keys(attrs).forEach(function (k) {
      if (k === "text") { node.textContent = attrs[k]; }
      else if (k.slice(0, 2) === "on") { node.addEventListener(k.slice(2), attrs[k]); }
      else { node.setAttribute(k, attrs[k]); }
    });
    (children || []).forEach(function (c) {
      node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return node;
  }

  function table(rows) {
    if (!rows || !rows.length) return el("p", { "class": "empty", text: "No rows." });
    var cols = Object.keys(rows[0]);
    var t = el("table");
    var head = el("tr");
    cols.forEach(function (c) { head.appendChild(el("th", { text: c })); });
    t.appendChild(head);
    rows.forEach(function (r) {
      var tr = el("tr");
      cols.forEach(function (c) { tr.appendChild(el("td", { text: String(r[c]) })); });
      t.appendChild(tr);
    });
    return t;
  }

  function view(name, render) {
    views.push({ name: name, render: render });
  }

  function show(v) {
    current = v;
    var main = document.getElementById("main");
    main.innerHTML = "";
    Array.prototype.forEach.call(document.querySelectorAll("#nav button"), function (b) {
      b.className = b.textContent === v.name ? "active" : "";
    });
    try {
      var out = v.render(main);
      if (out && typeof out.catch === "function") {
        out.catch(function (e) {
          main.appendChild(el("p", { "class": "error", text: String(e.message || e) }));
          status(String(e.message || e), "error");
        });
      }
    } catch (e) {
      main.appendChild(el("p", { "class": "error", text: String(e.message || e) }));
    }
  }

  /* Fetch the view manifest and inject each view's script tag, then
   * start. Views register themselves as they load, exactly as they
   * would if index.html had listed them -- but index.html never has to.
   */
  function boot() {
    return api("/api/views").then(function (m) {
      var names = (m && m.views) || [];
      return names.reduce(function (chain, name) {
        return chain.then(function () {
          return new Promise(function (resolve) {
            var s = document.createElement("script");
            s.src = "views/" + name;
            s.onload = resolve;
            s.onerror = function () {
              status("failed to load view " + name, "error");
              resolve();
            };
            document.head.appendChild(s);
          });
        });
      }, Promise.resolve());
    }).catch(function () {
      status("could not load view manifest", "error");
    }).then(start);
  }

  function start() {
    var nav = document.getElementById("nav");
    nav.innerHTML = "";
    if (!views.length) {
      document.getElementById("main").innerHTML =
        "<p class='empty'>No views registered yet. Add one in web/views/.</p>";
      status("no views");
      return;
    }
    views.forEach(function (v) {
      nav.appendChild(el("button", { text: v.name, onclick: function () { show(v); } }));
    });
    api("/api/health").then(function (h) {
      status((h.routes || []).length + " route(s) available");
    }).catch(function () { status("api unreachable", "error"); });
    show(views[0]);
  }

  return { api: api, view: view, start: start, boot: boot, el: el, table: table, status: status };
})();
