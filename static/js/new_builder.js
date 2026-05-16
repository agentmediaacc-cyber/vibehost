const $ = id => document.getElementById(id);
let current = 0;
const slides = [...document.querySelectorAll(".slide")];

const data = {
  "retail-shop": ["Retail Shop","Products / Adverts",["Featured Product","Promotion","New Arrival"]],
  "restaurant-food": ["Restaurant & Food","Popular Menu",["Lunch Special","Family Combo","Catering Tray"]],
  "transport-shuttle": ["Transport & Shuttle","Routes & Services",["Airport Transfer","Town Shuttle","School Transport"]],
  "guesthouse-lodge": ["Guesthouse & Lodge","Rooms",["Standard Room","Family Room","Executive Suite"]],
  "salon-beauty": ["Salon & Beauty","Beauty Services",["Hair Styling","Nails","Makeup Package"]],
  "school-education": ["School & Education","Programs",["Admissions","Classes","Notices"]],
  "health-wellness": ["Health & Wellness","Health Services",["Consultation","Wellness Plan","Pharmacy Support"]],
  "construction": ["Construction","Project Services",["House Building","Renovation","Repairs"]],
  "cleaning-services": ["Cleaning Services","Cleaning Packages",["Home Cleaning","Office Cleaning","Deep Cleaning"]]
};

function slug(v){return (v||"").toLowerCase().replace(/[^a-z0-9]+/g,"").slice(0,40)}
function chosen(){return document.querySelector("input[name='template_slug']:checked")?.value || "retail-shop"}

function show(i){
  current = Math.max(0, Math.min(slides.length-1, i));
  slides.forEach((s,idx)=>s.classList.toggle("active", idx===current));
  $("bar").style.width = ((current+1)/slides.length*100)+"%";
  $("back").style.visibility = current===0 ? "hidden" : "visible";
  $("next").style.display = current===slides.length-1 ? "none" : "block";
  update();
}

function update(){
  const d = data[chosen()] || data["retail-shop"];
  const name = $("businessName").value || "Your Business Name";
  const desc = $("description").value || "Your website preview will update while you type.";
  const sub = slug($("subdomain").value || name) || "yourbusiness";

  $("previewCategory").textContent = d[0];
  $("cardsTitle").textContent = d[1];
  $("previewName").textContent = name;
  $("previewDesc").textContent = desc;
  $("previewDomain").textContent = sub + ".namvibe.com";

  $("dynamicCards").innerHTML = d[2].map(x => `<div class="mini">${x}</div>`).join("");

  const primary = $("primaryColor").value;
  const secondary = $("secondaryColor").value;
  const accent = $("accentColor").value;
  const wall = $("wallpaperStyle").value;

  let bg = `linear-gradient(135deg,${primary},#020617)`;
  if(wall==="gradient") bg = `radial-gradient(circle at top left,${accent},transparent 30%),linear-gradient(135deg,${primary},${secondary})`;
  if(wall==="dark") bg = `linear-gradient(135deg,#020617,${primary})`;
  if(wall==="light") bg = `linear-gradient(135deg,#f8fafc,${accent})`;
  if(wall==="photo") bg = `linear-gradient(rgba(2,6,23,.65),rgba(2,6,23,.75)),url('https://images.unsplash.com/photo-1497366754035-f200968a6e72?auto=format&fit=crop&w=1400&q=80') center/cover`;

  $("hero").style.background = bg;
  document.querySelectorAll(".actions a").forEach(a=>a.style.background=secondary);

  const h = $("headingStyle").value;
  $("previewName").style.fontFamily =
    h==="classic" ? "Georgia,serif" :
    h==="friendly" ? "Trebuchet MS,Arial,sans-serif" :
    h==="advert" ? "Impact,Arial Black,sans-serif" :
    "-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif";

  $("productsCard").style.display = $("showProducts").checked ? "block" : "none";
  $("bookingCard").style.display = $("showBooking").checked ? "block" : "none";
  $("galleryCard").style.display = $("showGallery").checked ? "block" : "none";
  $("whatsappBtn").style.display = $("showWhatsapp").checked ? "inline-flex" : "none";
}

document.querySelectorAll("input,select,textarea").forEach(el=>{
  el.addEventListener("input", update);
  el.addEventListener("change", update);
});

$("businessName").addEventListener("input",()=>{
  if(!$("subdomain").dataset.touched) $("subdomain").value = slug($("businessName").value);
});
$("subdomain").addEventListener("input",()=> $("subdomain").dataset.touched="1");

$("next").onclick = ()=>show(current+1);
$("back").onclick = ()=>show(current-1);

show(0);
