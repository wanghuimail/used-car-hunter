function formatMoney(value) {
  return "$" + Number(value).toLocaleString("en-CA", { maximumFractionDigits: 0 });
}

function formatMoneyCents(value) {
  return "$" + Number(value).toLocaleString("en-CA", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function renderTrimBar(ladder, activeIndex, trimRaw) {
  if (!ladder || ladder.length === 0) {
    return '<p class="meta">Trim ladder not available for this model.</p>';
  }

  const steps = ladder
    .map((name, index) => {
      const active = index === activeIndex ? " active" : "";
      return `<span class="trim-step${active}">${name}</span>`;
    })
    .join("");

  const note =
    activeIndex === null || activeIndex === undefined
      ? `<p class="meta">Listed as: <strong>${trimRaw || "Unknown trim"}</strong> (not matched to a standard trim step)</p>`
      : `<p class="meta">Matched trim: <strong>${ladder[activeIndex]}</strong>${trimRaw ? ` · listing text: ${trimRaw}` : ""}</p>`;

  return `<div class="trim-bar">${steps}</div>${note}`;
}

function renderDriveAwayTable(da) {
  return `
    <table class="modal-table">
      <tbody>
        <tr><td>Advertised price</td><td>${formatMoney(da.list_price)}</td></tr>
        <tr><td>HST (13%)</td><td>${formatMoneyCents(da.hst)}</td></tr>
        <tr><td>OMVIC</td><td>${formatMoneyCents(da.omvic)}</td></tr>
        <tr><td>Registration</td><td>${formatMoney(da.registration)}</td></tr>
        <tr><td>Miscellaneous</td><td>${formatMoney(da.miscellaneous)}</td></tr>
        <tr><td>Dealer/admin fee</td><td>${formatMoney(da.dealer_fee)}</td></tr>
        <tr class="total"><td>Estimated drive-away</td><td>${formatMoney(da.drive_away)}</td></tr>
      </tbody>
    </table>
  `;
}

function openDetailModal(detail) {
  const modal = document.getElementById("detail-modal");
  const title = document.getElementById("modal-title");
  const body = document.getElementById("modal-body");

  title.textContent = detail.title + (detail.trim_matched ? ` · ${detail.trim_matched}` : "");

  const reasons = (detail.reasons || [])
    .map((reason) => `<li>${reason}</li>`)
    .join("");

  body.innerHTML = `
    <section class="modal-section">
      <h3>Is it a good deal?</h3>
      <p class="deal-score-value">${detail.deal_score}</p>
      <p class="deal-score-label">${detail.deal_label}</p>
      <p class="meta">${detail.deal_summary}</p>
    </section>

    <section class="modal-section">
      <h3>How much do I actually pay?</h3>
      <p class="drive-away-highlight">${formatMoney(detail.drive_away.drive_away)}</p>
      <p class="meta">Estimated Ontario drive-away price</p>
      ${renderDriveAwayTable(detail.drive_away)}
    </section>

    <section class="modal-section">
      <h3>What trim is it?</h3>
      ${renderTrimBar(detail.trim_ladder, detail.trim_index, detail.trim_raw)}
    </section>

    <section class="modal-section">
      <h3>Why is it recommended?</h3>
      <ul class="reason-list">${reasons}</ul>
    </section>

    <div class="modal-actions">
      <a class="btn" href="${detail.listing_url}" target="_blank" rel="noopener">Open dealer listing</a>
      <button type="button" class="btn secondary" id="modal-close-btn">Close</button>
    </div>
  `;

  document.getElementById("modal-close-btn").addEventListener("click", closeDetailModal);
  modal.hidden = false;
  document.body.classList.add("modal-open");
}

function closeDetailModal() {
  const modal = document.getElementById("detail-modal");
  modal.hidden = true;
  document.body.classList.remove("modal-open");
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".details-btn").forEach((button) => {
    button.addEventListener("click", () => {
      const payload = button.getAttribute("data-detail");
      if (!payload) return;
      try {
        openDetailModal(JSON.parse(payload));
      } catch (error) {
        console.error("Could not open car details:", error);
        alert("Sorry, car details could not be loaded. Please refresh the page.");
      }
    });
  });

  document.querySelector(".modal-backdrop")?.addEventListener("click", closeDetailModal);
  document.querySelector(".modal-close")?.addEventListener("click", closeDetailModal);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeDetailModal();
    }
  });
});
