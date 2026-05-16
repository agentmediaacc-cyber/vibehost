const $ = id => document.getElementById(id);
let currentSlide = 0;
const slides = [...document.querySelectorAll(".slide")];

const templateData = {
  "restaurant-food": ["Restaurant & Food","Fresh meals, takeaways and catering made simple.","Popular Menu",["Lunch Special","Family Combo","Catering Tray"],"Order / Reservation","Food Gallery"],
  "transport-shuttle": ["Transport & Shuttle","Reliable rides, airport transfers and shuttle bookings.","Routes & Services",["Airport Transfer","Town Shuttle","School Transport"],"Request a Ride","Fleet Gallery"],
  "guesthouse-lodge": ["Guesthouse & Accommodation","Comfortable rooms and peaceful stays for every guest.","Rooms",["Standard Room","Family Room","Executive Suite"],"Book a Stay","Room Gallery"],
  "retail-shop": ["Retail Shop","Shop products, promotions and new arrivals online.","Products / Adverts",["Featured Product","Promotion","New Arrival"],"Customer Enquiry","Product Gallery"],
  "beauty-salon": ["Salon & Beauty","Beauty, grooming and self-care services made easy.","Beauty Services",["Hair Styling","Nails & Makeup","Beauty Package"],"Book Appointment","Beauty Gallery"],
  "construction": ["Construction","Professional building, repairs and project services.","Project Services",["House Building","Renovations","Maintenance"],"Request Quote","Project Gallery"],
  "cleaning-services": ["Cleaning Services","Clean homes, offices and business spaces with trusted care.","Cleaning Packages",["Home Cleaning","Office Cleaning","Deep Cleaning"],"Book Cleaning","Before & After"],
  "health-wellness": ["Health & Wellness","Care, wellness and health support for your community.","Wellness Services",["Consultation","Therapy Session","Wellness Plan"],"Book Consultation","Wellness Gallery"]
};

function slugify(v){return (v||"").toLowerCase().replace(/[^a-z0-9]+/g,"").slice(0,40)}
function selectedTemplate(){return document.querySelector("input[name='template_slug']:checked")?.value || "retail-shop"}
function data(){return templateData[selectedTemplate()] || templateData["retail-shop"]}

function showSlide(i){
  currentSlide = Math.max(0, Math.min(slides.length - 1, i));
  slides.forEach((s,idx)=>s.classList.toggle("active", idx===currentSlide));
  $("progressFill").style.width = ((currentSlide+1)/slides.length*100)+"%";
  $("prevBtn").style.visibility = currentSlide === 0 ? "hidden" : "visible";
  $("nextBtn").style.display = currentSlide === slides.length-1 ? "none" : "block";
  updatePreview();
}

function updatePreview(){
  const d = data();
  $("category").value = d[0];

  const name = $("businessName").value || "Your Business Name";
  const desc = $("description").value || d[1];
  const town = $("town").value || "Windhoek";
  const sub = slugify($("subdomain").value || name) || "yourbusiness";

  $("previewName").textContent = name;
  $("previewDescription").textContent = desc;
  $("previewCategory").textContent = `${d[0]} • ${town}`;
  $("liveDomain").textContent = `${sub}.namvibe.com`;
  $("cardsTitle").textContent = d[2];
  $("bookingCardTitle").textContent = d[4];
  $("galleryCardTitle").textContent = d[5];

  $("productGrid").innerHTML = "";
  d[3].forEach(x=>{
    $("productGrid").innerHTML += `<div class="product-card"><b>${x}</b><small>Editable in dashboard</small></div>`;
  });
  $("productGrid").innerHTML += `<div class="product-card locked-card"><b>More locked</b><small>Upgrade for unlimited</small></div>`;

  const primary = $("primaryColor").value;
  const secondary = $("secondaryColor").value;
  const accent = $("accentColor").value;
  const wall = $("wallpaperStyle").value;

  let bg = `linear-gradient(135deg, ${primary}, #020617)`;
  if(wall==="gradient") bg = `radial-gradient(circle at top left, ${accent}, transparent 30%),linear-gradient(135deg,${primary},${secondary})`;
  if(wall==="dark") bg = `linear-gradient(135deg,#020617,${primary})`;
  if(wall==="soft") bg = `linear-gradient(135deg,#f8fafc,${accent})`;
  if(wall==="image") bg = `linear-gradient(rgba(2,6,23,.65),rgba(2,6,23,.75)),url('https://images.unsplash.com/photo-1497366754035-f200968a6e72?auto=format&fit=crop&w=1400&q=80') center/cover`;

  $("siteHero").style.background = bg;
  document.querySelectorAll(".actions a").forEach(a=>a.style.background=secondary);

  const heading = $("headingStyle").value;
  $("previewName").style.fontFamily =
    heading==="classic" ? "Georgia,serif" :
    heading==="bold" ? "Impact,Arial Black,sans-serif" :
    heading==="soft" ? "Trebuchet MS,Arial,sans-serif" :
    "-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif";

  document.querySelector(".preview-frame").style.fontFamily =
    $("fontStyle").value==="luxury" ? "Georgia,serif" :
    $("fontStyle").value==="friendly" ? "Trebuchet MS,Arial,sans-serif" :
    "-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif";

  $("servicesCard").style.display = $("showServices").checked ? "block" : "none";
  $("galleryCard").style.display = $("showGallery").checked ? "block" : "none";
  $("bookingCard").style.display = $("showBooking").checked ? "block" : "none";
}

document.querySelectorAll("input,select,textarea").forEach(el=>{
  el.addEventListener("input", updatePreview);
  el.addEventListener("change", updatePreview);
});

$("businessName").addEventListener("input",()=>{
  if(!$("subdomain").dataset.touched) $("subdomain").value = slugify($("businessName").value);
});
$("subdomain").addEventListener("input",()=> $("subdomain").dataset.touched="1");

$("logoInput").addEventListener("change",function(){
  const file=this.files[0];
  if(!file)return;
  const reader=new FileReader();
  reader.onload=e=>{
    $("previewLogo").src=e.target.result;
    $("previewLogo").style.display="inline-block";
  };
  reader.readAsDataURL(file);
});

$("nextBtn").onclick=()=>showSlide(currentSlide+1);
$("prevBtn").onclick=()=>showSlide(currentSlide-1);

showSlide(0);
