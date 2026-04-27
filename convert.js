const fs = require("fs");

const data = JSON.parse(fs.readFileSync("output_detail_v2.json", "utf-8"));

const formatted = data.map(item => ({
  id: item.id,
  title: item.title,
  location: item.location,
  price: item.price,
  latitude: item.latitude,
  longitude: item.longitude,
  characteristics: JSON.stringify(item.characteristics) // 🔥 чухал хэсэг
}));

const headers = Object.keys(formatted[0]);

const csvRows = [
  headers.join(","),
  ...formatted.map(row =>
    headers.map(field => {
      let value = row[field] ?? "";

      if (typeof value === "object") {
        value = JSON.stringify(value);
      }

      value = String(value).replace(/"/g, '""'); // escape хийх
      return `"${value}"`;
    }).join(",")
  )
];

fs.writeFileSync("output_v2.csv", csvRows.join("\n"), "utf-8");

console.log("Supabase-д бэлэн CSV үүсгэлээ ✅");