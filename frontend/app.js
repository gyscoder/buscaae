const API_URL = "http://localhost:8000/search";

async function searchBooks() {

  const status = document.getElementById("status");
  const resultsDiv = document.getElementById("results");

  resultsDiv.innerHTML = "";
  status.innerText = "Buscando...";

  const body = {
    title: document.getElementById("title").value || null,
    frase: document.getElementById("frase").value || null,
    author: document.getElementById("author").value || null,
    publisher: document.getElementById("publisher").value || null,
    year: document.getElementById("year").value || null,
    site: document.getElementById("site").value || null,
    filetypes: document.getElementById("filetypes").value
      ? document.getElementById("filetypes").value.split(",")
      : null
  };

  try {

    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });

    const data = await response.json();

    document.getElementById("dorkUsed").innerHTML =
      `<b>Dork utilizada:</b> ${data.query}`;

    status.innerText = `Encontrados ${data.total} resultados`;

    renderResults(data.results);

  } catch (err) {
    status.innerText = "Erro ao conectar com API";
    console.error(err);
  }
}


function renderResults(results) {

  const container = document.getElementById("results");
  container.innerHTML = "";

  results.forEach(r => {

    let badge = "🔗 Link";

    if (r.is_pdf) badge = "📄 PDF";
    else if (r.is_epub) badge = "📘 EPUB";
    else if (r.is_book) badge = "📚 Livro";
    if (r.is_drive && r.drive_type === "file") badge = "📄 Drive File";
    if (r.is_drive && r.drive_type === "folder") badge = "📂 Drive Folder";

    const card = document.createElement("div");

    card.className =
      "bg-gray-800 p-4 rounded-lg hover:bg-gray-700 transition";

    card.innerHTML = `
      <a href="${r.url}" target="_blank"
        class="text-xl text-blue-400 font-semibold">
        ${r.preview_title || r.title}
      </a>

      <p class="text-sm text-gray-400">
        ${r.source || ""} • ${badge}
      </p>

      <p class="text-sm text-gray-300 mt-2">
        ${r.preview_desc || r.snippet || ""}
      </p>

      <p class="text-xs text-gray-500 mt-1">
        ${r.author || ""} ${r.year ? "• " + r.year : ""}
      </p>

      ${r.collection ? `
        <a href="${r.collection}" target="_blank"
          class="text-green-400 text-xs block mt-2">
          📂 Ver todos arquivos
        </a>
      ` : ""}

      ${r.download ? `
        <a href="${r.download}" target="_blank"
          class="text-yellow-400 text-xs block mt-1">
          ⬇ Download direto
        </a>
      ` : ""}
      ${r.files ? r.files.map(f => `
        <a href="${f.url}" target="_blank"
          class="text-purple-400 text-xs block mt-1">
          📎 ${f.name}
        </a>
    `).join("") : ""}
      ${r.drive_type === "file" && r.drive_preview ? `
        <a href="${r.drive_preview}" target="_blank"
          class="text-green-400 text-xs block mt-2">
          👁 Preview
        </a>
      ` : ""}

      ${r.drive_type === "file" && r.drive_download ? `
        <a href="${r.drive_download}" target="_blank"
          class="text-green-300 text-xs block mt-1">
          ⬇ Download
        </a>
      ` : ""}
      ${r.drive_type === "folder" && r.drive_folder ? `
        <a href="${r.drive_folder}" target="_blank"
          class="text-green-400 text-xs block mt-2">
          📂 Abrir pasta
        </a>
      ` : ""}
    `;
    container.appendChild(card);
  });
}