const $ = (id) => document.getElementById(id);

const templateData = {
  "restaurant-food": {
    category: "Restaurant & Food",
    hero: "Fresh meals, takeaways and catering made simple.",
    cardsTitle: "Popular Menu",
    cards: ["Lunch Special", "Family Combo", "Catering Tray"],
    booking: "Order / Reservation",
    gallery: "Food Gallery"
  },
  "transport-shuttle": {
    category: "Transport & Shuttle",
    hero: "Reliable rides, airport transfers and shuttle bookings.",
    cardsTitle: "Routes & Services",
    cards: ["Airport Transfer", "Town Shuttle", "School Transport"],
    booking: "Request a Ride",
    gallery: "Fleet Gallery"
  },
  "guesthouse-lodge": {
    category: "Guesthouse & Accommodation",
    hero: "Comfortable rooms and peaceful stays for every guest.",
    cardsTitle: "Rooms",
    cards: ["Standard Room", "Family Room", "Executive Suite"],
    booking: "Book a Stay",
    gallery: "Room Gallery"
  },
  "retail-shop": {
    category: "Retail Shop",
    hero: "Shop products, promotions and new arrivals online.",
    cardsTitle: "Products / Adverts",
    cards: ["Featured Product", "Promotion", "New Arrival"],
    booking: "Customer Enquiry",
    gallery: "Product Gallery"
  },
  "beauty-salon": {
    category: "Salon & Beauty",
    hero: "Beauty, grooming and self-care services made easy.",
    cardsTitle: "Beauty Services",
    cards: ["Hair Styling", "Nails & Makeup", "Beauty Package"],
    booking: "Book Appointment",
    gallery: "Beauty Gallery"
  },
  "construction": {
    category: "Construction",
    hero: "Professional building, repairs and project services.",
    cardsTitle: "Project Services",
    cards: ["House Building", "Renovations", "Maintenance"],
    booking: "Request Quote",
    gallery: "Project Gallery"
  },
  "cleaning-services": {
    category: "Cleaning Services",
    hero: "Clean homes, offices and business spaces with trusted care.",
    cardsTitle: "Cleaning Packages",
    cards: ["Home Cleaning", "Office Cleaning", "Deep Cleaning"],
    booking: "Book Cleaning",
    gallery: "Before & After"
  },
  "health-wellness": {
    category: "Health & Wellness",
    hero: "Care, wellness and health support for your community.",
    cardsTitle: "Wellness Services",
    cards: ["Consultation", "Therapy Session", "Wellness Plan"],
    booking: "Book Consultation",
    gallery: "Wellness Gallery"
  },
  "school-education": {
    category: "School & Education",
    hero: "Learning programs, school updates and enrolment support.",
    cardsTitle: "School Sections",
    cards: ["Admissions", "Programs", "School Notices"],
    booking: "Enrol / Contact",
    gallery: "School Gallery"
  }
};

const fields = [
  "businessName","description","category","town","subdomain","email","phone","whatsapp",
  "primaryColor","secondaryColor","accentColor","fontStyle","headingStyle","pictureStyle","wallpaperStyle",
  "showServices","showGallery","showBooking","showWhatsapp"
];

function slugify(value){
  return (value || "").toLowerCase().replace(/[^a-z0-9]+/g,"").slice(0,40);
}

function selectedTemplate(){
  const checked = document.querySelector("input[name='template_slug']:checked");
  return checked ? checked.value : "retail-shop";
}

function getTemplate(){
  return templateData[selectedTemplate()] || templateData["retail-shop"];
}

function updateCards(data){
  $("cardsTitle").textContent = data.cardsTitle;
  const grid = $("productGrid");
  grid.innerHTML = "";
  data.cards.forEach((item, index) => {
    const div = document.createElement("div");
    div.className = "product-card";
    div.innerHTML = `<b>${item}</b><small>${index === 2 ? "Free trial visible card" : "Editable in dashboard"}</small>`;
    grid.appendChild(div);
  });

  const locked = document.createElement("div");
  locked.className = "product-card locked-card";
  locked.innerHTML = "<b>More cards locked</b><small>Upgrade to add unlimited cards</small>";
  grid.appendChild(locked);
}

function updatePreview(){
  const data = getTemplate();

  if ($("category")) $("category").value = data.category;

  const name = $("businessName").value || "Your Business Name";
  const desc = $("description").value || data.hero;
  const category = $("category").value || data.category;
  const town = $("town").value || "Windhoek";
  const subdomain = slugify($("subdomain").value || name) || "yourbusiness";

  $("previewName").textContent = name;
  $("previewDescription").textContent = desc;
  $("previewCategory").textContent = `${category} • ${town}`;
  $("liveDomain").textContent = `${subdomain}.namvibe.com`;

  $("servicesCardTitle").textContent = data.cardsTitle;
  $("servicesCardText").textContent = `Showcase your ${data.category.toLowerCase()} offers with clear prices and descriptions.`;
  $("bookingCardTitle").textContent = data.booking;
  $("galleryCardTitle").textContent = data.gallery;

  updateCards(data);

  const primary = $("primaryColor").value;
  const secondary = $("secondaryColor").value;
  const accent = $("accentColor").value;
  const wallpaper = $("wallpaperStyle").value;
  const font = $("fontStyle").value;
  const heading = $("headingStyle").value;
  const picture = $("pictureStyle").value;

  let bg = `linear-gradient(135deg, ${primary}, #020617)`;
  if(wallpaper === "gradient") bg = `radial-gradient(circle at top left, ${accent}, transparent 30%), linear-gradient(135deg, ${primary}, ${secondary})`;
  if(wallpaper === "dark") bg = `linear-gradient(135deg, #020617, ${primary})`;
  if(wallpaper === "soft") bg = `linear-gradient(135deg, #f8fafc, ${accent})`;
  if(wallpaper === "image") bg = `linear-gradient(rgba(2,6,23,.62), rgba(2,6,23,.72)), url('https://images.unsplash.com/photo-1497366754035-f200968a6e72?auto=format&fit=crop&w=1400&q=80') center/cover`;

  $("siteHero").style.background = bg;

  document.querySelectorAll(".hero-actions a").forEach(a => {
    a.style.background = secondary;
  });

  $("previewName").style.fontFamily =
    heading === "classic" ? "Georgia, serif" :
    heading === "bold" ? "Impact, Arial Black, sans-serif" :
    heading === "soft" ? "Trebuchet MS, Arial, sans-serif" :
    "-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif";

  document.querySelector(".preview-phone").style.fontFamily =
    font === "luxury" ? "Georgia, serif" :
    font === "friendly" ? "Trebuchet MS, Arial, sans-serif" :
    "-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif";

  document.querySelectorAll(".product-card").forEach(card => {
    card.classList.remove("image-round","image-square","image-banner");
    card.classList.add(`image-${picture}`);
  });

  $("servicesCard").style.display = $("showServices").checked ? "block" : "none";
  $("galleryCard").style.display = $("showGallery").checked ? "block" : "none";
  $("bookingCard").style.display = $("showBooking").checked ? "block" : "none";

  const completed = fields.filter(id => {
    const el = $(id);
    if(!el) return false;
    if(el.type === "checkbox") return el.checked;
    return el.value && el.value.trim() !== "";
  }).length;

  $("progressFill").style.width = Math.min(100, 15 + completed * 5) + "%";
}

fields.forEach(id => {
  const el = $(id);
  if(el){
    el.addEventListener("input", updatePreview);
    el.addEventListener("change", updatePreview);
  }
});

document.querySelectorAll("input[name='template_slug']").forEach(el => {
  el.addEventListener("change", updatePreview);
});

$("logoInput").addEventListener("change", function(){
  const file = this.files[0];
  if(!file) return;
  const reader = new FileReader();
  reader.onload = e => {
    $("previewLogo").src = e.target.result;
    $("previewLogo").style.display = "inline-block";
  };
  reader.readAsDataURL(file);
});

$("businessName").addEventListener("input", function(){
  if(!$("subdomain").dataset.touched){
    $("subdomain").value = slugify(this.value);
  }
});
$("subdomain").addEventListener("input", function(){
  this.dataset.touched = "1";
});

updatePreview();
