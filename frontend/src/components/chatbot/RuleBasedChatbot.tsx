import React, { useState, useRef, useEffect } from "react";

interface RuleBasedChatbotProps {
  language: string;
}

interface Message {
  sender: "bot" | "user";
  text: string;
  options?: string[];
}

// ── Translations ─────────────────────────────────────────────────────────────
type LangKey = "English" | "Hindi" | "Telugu" | "Bengali" | "Tamil" | "Marathi";

const T: Record<LangKey, Record<string, string>> = {
  English: {
    greeting:
      "Hi! 👋 I'm your **CustomerSetu** guide.\nI'll help you register, track, and understand your complaint journey.\n\nWhat would you like to do?",
    menu_register: "📝 Register a complaint",
    menu_track: "🔍 Track my complaint",
    menu_how: "🤖 How does AI process it?",
    menu_escalate: "🔺 Escalation & my rights",
    menu_channels: "📡 Available channels",
    menu_rbi: "⚖️ RBI guidelines & TAT",
    menu_categories: "📂 Complaint categories",
    menu_back: "⬅️ Main menu",

    register_intro:
      "You can register a complaint via **5 channels**:\n\n" +
      "1️⃣ **Web** — Dashboard → Submit Complaint\n" +
      "2️⃣ **Email** — Send to bank email (auto-read every 30s)\n" +
      "3️⃣ **WhatsApp** — Message our Twilio number\n" +
      "4️⃣ **Branch** — Walk-in, agent logs via Agent Desk\n" +
      "5️⃣ **Mobile App** — In-app complaint form\n\n" +
      "You'll get a **Complaint ID** (e.g. CMP-A1B2C3D4) instantly.",

    register_what_needed:
      "To register you'll need:\n\n" +
      "• **Customer ID** (account no. or CIF)\n" +
      "• **Issue description** (min 10 chars)\n" +
      "• **Channel** (web / email / WhatsApp)\n" +
      "• Optional: **Screenshot** (max 10 MB)\n\n" +
      "Keep your Complaint ID for tracking.",

    how_pipeline:
      "**Your complaint goes through 9 AI steps:**\n\n" +
      "1. 🔒 **PII Masking** — Aadhaar, phone, name hidden before AI sees it\n" +
      "2. 🔍 **Duplicate Check** — Finds if same issue was already filed\n" +
      "3. 🏷️ **Classification** — GPT-4o assigns category (UPI, ATM, Loan…)\n" +
      "4. 💬 **Sentiment** — Urgency score 1–10 assigned\n" +
      "5. ⚖️ **RBI Compliance** — Checked against 14 regulatory categories\n" +
      "6. 📚 **Knowledge Base** — Top 3 similar resolved cases retrieved\n" +
      "7. ✍️ **Resolution Draft** — AI writes response with root cause\n" +
      "8. ✅ **Fact Check** — AI verifies its own response\n" +
      "9. 🔀 **Routing** — AUTO send / HUMAN review / ESCALATE\n\n" +
      "Every step is **fully explained** — no black box.",

    escalation_info:
      "**Your complaint auto-escalates if unresolved:**\n\n" +
      "🟢 Tier 0 — Standard (any branch)\n" +
      "🔵 Tier 1 — Branch Manager\n" +
      "🟡 Tier 2 — Zonal Office\n" +
      "🟠 Tier 3 — Regional Office\n" +
      "🔴 Tier 4 — Head Office / Nodal Officer\n" +
      "🟣 Tier 5 — RBI Banking Ombudsman\n\n" +
      "**Triggers:** AI confidence < 75%, fraud detected, you mention 'CEO'/'ombudsman', SLA breach.\n" +
      "Max 5 hops. You get updates at every tier.",

    channels_info:
      "**5 channels — same AI pipeline for all:**\n\n" +
      "🌐 Web form · 📧 Email (30s poll) · 📱 WhatsApp\n" +
      "🏢 Branch walk-in · 📲 Mobile app\n\n" +
      "Priority is equal regardless of channel.",

    rbi_info:
      "**Key RBI timelines:**\n\n" +
      "• ATM/UPI failed → reversal in T+1 to T+5 days\n" +
      "• Unauthorised debit → provisional credit in 10 days\n" +
      "• Property docs after loan closure → 30 days\n" +
      "• CIBIL correction → 30 days\n" +
      "• Recovery agent harassment → immediate human review\n\n" +
      "**Penalty:** ₹100/day for TAT breach.\n" +
      "Unresolved after 30 days → RBI Ombudsman:\nbankingombudsman.rbi.org.in",

    categories_info:
      "**Categories we handle:**\n\n" +
      "💳 UPI · IMPS · NEFT · ATM\n" +
      "💳 Debit Card · Credit Card\n" +
      "🏦 Savings · Current · Fixed Deposit\n" +
      "🏠 Home · Personal · Business · Vehicle Loan\n" +
      "📱 Internet Banking · Mobile Banking\n" +
      "📋 KYC · Cheque · Locker · Insurance\n" +
      "💱 Forex · Mutual Fund · Gold Loan\n" +
      "🚨 Fraud / Unauthorised Transaction",

    track_info:
      "**To track your complaint:**\n\n" +
      "You need your **Complaint ID** (CMP-XXXXXXXX)\n\n" +
      "Go to **Complaints tab** on the dashboard and search by ID.\n\n" +
      "You can see:\n" +
      "• Current status & tier\n" +
      "• Which agent is handling it\n" +
      "• SLA deadline remaining\n" +
      "• Full AI reasoning for every decision\n" +
      "• Complete escalation history",

    not_understood:
      "I didn't catch that. Try one of the options below, or type a keyword like **complaint**, **track**, **UPI**, **ATM**, **loan**, **escalate**, **RBI**, **fraud**.",

    followup: "Is there anything else I can help you with?",
    goodbye:
      "Thanks for using **CustomerSetu**! 🙏\nFor urgent help call **1800 22 2244** (24×7 free).",
  },

  Hindi: {
    greeting:
      "नमस्ते! 👋 मैं **CustomerSetu** गाइड हूँ।\nमैं शिकायत दर्ज करने, ट्रैक करने और समझने में मदद करूँगा।\n\nआप क्या करना चाहते हैं?",
    menu_register: "📝 शिकायत दर्ज करें",
    menu_track: "🔍 शिकायत ट्रैक करें",
    menu_how: "🤖 AI कैसे प्रोसेस करता है?",
    menu_escalate: "🔺 एस्केलेशन और मेरे अधिकार",
    menu_channels: "📡 उपलब्ध चैनल",
    menu_rbi: "⚖️ RBI नियम और TAT",
    menu_categories: "📂 शिकायत श्रेणियाँ",
    menu_back: "⬅️ मुख्य मेनू",

    register_intro:
      "शिकायत दर्ज करने के **5 तरीके**:\n\n" +
      "1️⃣ **वेब** — डैशबोर्ड पर Submit Complaint\n" +
      "2️⃣ **ईमेल** — बैंक ईमेल पर भेजें (हर 30 सेकंड में जाँच)\n" +
      "3️⃣ **WhatsApp** — हमारे नंबर पर मैसेज\n" +
      "4️⃣ **शाखा** — एजेंट Agent Desk पर दर्ज करेगा\n" +
      "5️⃣ **मोबाइल ऐप** — ऐप में फॉर्म भरें\n\n" +
      "तुरंत **Complaint ID** (जैसे CMP-A1B2C3D4) मिलेगा।",

    register_what_needed:
      "शिकायत के लिए जरूरी:\n\n" +
      "• **ग्राहक ID** (खाता नंबर या CIF)\n" +
      "• **समस्या विवरण** (न्यूनतम 10 अक्षर)\n" +
      "• **चैनल** (वेब / ईमेल / WhatsApp)\n" +
      "• वैकल्पिक: **स्क्रीनशॉट** (अधिकतम 10 MB)",

    how_pipeline:
      "**शिकायत 9 AI चरणों से गुजरती है:**\n\n" +
      "1. 🔒 PII मास्किंग — नाम, आधार छिपाए जाते हैं\n" +
      "2. 🔍 डुप्लीकेट जाँच\n" +
      "3. 🏷️ वर्गीकरण — GPT-4o श्रेणी देता है\n" +
      "4. 💬 भावना विश्लेषण — तात्कालिकता 1–10\n" +
      "5. ⚖️ RBI अनुपालन जाँच\n" +
      "6. 📚 नॉलेज बेस खोज\n" +
      "7. ✍️ समाधान ड्राफ्ट\n" +
      "8. ✅ तथ्य जाँच\n" +
      "9. 🔀 रूटिंग — स्वत: / मानव / एस्केलेशन\n\n" +
      "हर कदम **पारदर्शी** है।",

    escalation_info:
      "**एस्केलेशन पथ:**\n\n" +
      "🟢 Tier 0 → 🔵 Tier 1 (शाखा) → 🟡 Tier 2 (क्षेत्र) → 🟠 Tier 3 (रीजन) → 🔴 Tier 4 (मुख्यालय) → 🟣 Tier 5 (RBI लोकपाल)\n\n" +
      "अधिकतम 5 एस्केलेशन। प्रत्येक स्तर पर अपडेट मिलेगा।",

    channels_info:
      "**5 चैनल — सभी एक ही AI पाइपलाइन:**\n\nवेब · ईमेल · WhatsApp · शाखा · मोबाइल ऐप",

    rbi_info:
      "**RBI समय-सीमाएँ:**\n\n" +
      "• ATM/UPI विफल → T+5 दिन में वापसी\n" +
      "• अनधिकृत लेनदेन → 10 दिन में क्रेडिट\n" +
      "• संपत्ति दस्तावेज → 30 दिन में\n" +
      "• TAT उल्लंघन → ₹100/दिन जुर्माना\n" +
      "30 दिन बाद: bankingombudsman.rbi.org.in",

    categories_info:
      "**श्रेणियाँ:** UPI · ATM · डेबिट/क्रेडिट कार्ड · बचत/चालू खाता · गृह/व्यक्तिगत ऋण · इंटरनेट/मोबाइल बैंकिंग · KYC · बीमा · धोखाधड़ी",

    track_info:
      "**शिकायत ट्रैक करें:**\n\nComplaint ID (CMP-XXXXXXXX) से डैशबोर्ड के Complaints टैब में खोजें।\n\nआप देख सकते हैं: स्थिति · Tier · एजेंट · SLA · AI तर्क",

    not_understood:
      "समझ नहीं आया। नीचे से विकल्प चुनें या लिखें: **शिकायत**, **ट्रैक**, **UPI**, **ATM**, **RBI**",

    followup: "क्या और कोई मदद चाहिए?",
    goodbye: "धन्यवाद! 🙏 हेल्पलाइन: **1800 22 2244** (24×7 निःशुल्क)",
  },

  Telugu: {
    greeting:
      "నమస్కారం! 👋 నేను **CustomerSetu** గైడ్.\nఫిర్యాదు నమోదు, ట్రాక్ మరియు అర్థం చేసుకోవడంలో సహాయం చేస్తాను.\n\nమీకు ఏమి కావాలి?",
    menu_register: "📝 ఫిర్యాదు నమోదు",
    menu_track: "🔍 ట్రాక్ చేయండి",
    menu_how: "🤖 AI ఎలా పని చేస్తుంది?",
    menu_escalate: "🔺 ఎస్కలేషన్ & హక్కులు",
    menu_channels: "📡 ఛానెల్‌లు",
    menu_rbi: "⚖️ RBI నిబంధనలు",
    menu_categories: "📂 వర్గాలు",
    menu_back: "⬅️ ప్రధాన మెనూ",
    register_intro:
      "**5 మార్గాల్లో ఫిర్యాదు:**\n1️⃣ వెబ్ · 2️⃣ ఇమెయిల్ (30s) · 3️⃣ WhatsApp · 4️⃣ శాఖ · 5️⃣ మొబైల్\nCMP-XXXXXXXX ID వెంటనే వస్తుంది.",
    register_what_needed:
      "అవసరం: కస్టమర్ ID · సమస్య వివరణ · ఛానెల్ · స్క్రీన్‌షాట్ (ఐచ్ఛికం)",
    how_pipeline:
      "**9 AI దశలు:** PII → డూప్లికేట్ → వర్గీకరణ → సెంటిమెంట్ → RBI → KB → రిజల్యూషన్ → ఫ్యాక్ట్ చెక్ → రూటింగ్\nప్రతి దశ పారదర్శకంగా ఉంటుంది.",
    escalation_info:
      "Tier 0→1→2→3→4→5 (RBI Ombudsman)\nగరిష్టంగా 5 హాప్స్. ప్రతి స్థాయిలో నోటిఫికేషన్.",
    channels_info: "వెబ్ · ఇమెయిల్ · WhatsApp · శాఖ · మొబైల్ (అన్నీ ఒకే AI)",
    rbi_info: "ATM/UPI T+5 రోజుల్లో రివర్సల్. TAT మీరడంపై ₹100/రోజు జరిమానా.",
    categories_info:
      "UPI · ATM · కార్డులు · రుణాలు · ఖాతాలు · KYC · బీమా · మోసం",
    track_info: "Complaint ID తో డ్యాష్‌బోర్డ్ Complaints టాబ్‌లో వెతకండి.",
    not_understood: "అర్థం కాలేదు. క్రింది ఎంపికలు చేయండి.",
    followup: "మరేమైనా సహాయం?",
    goodbye: "ధన్యవాదాలు! 🙏 హెల్ప్‌లైన్: **1800 22 2244**",
  },

  Bengali: {
    greeting:
      "নমস্কার! 👋 আমি **CustomerSetu** গাইড।\nঅভিযোগ নথিভুক্ত, ট্র্যাক ও বুঝতে সাহায্য করব।\n\nআপনার কী প্রয়োজন?",
    menu_register: "📝 অভিযোগ নথিভুক্ত",
    menu_track: "🔍 ট্র্যাক করুন",
    menu_how: "🤖 AI কীভাবে কাজ করে?",
    menu_escalate: "🔺 এস্কেলেশন ও অধিকার",
    menu_channels: "📡 চ্যানেলসমূহ",
    menu_rbi: "⚖️ RBI নির্দেশিকা",
    menu_categories: "📂 বিভাগসমূহ",
    menu_back: "⬅️ প্রধান মেনু",
    register_intro:
      "**৫টি চ্যানেলে অভিযোগ:**\n১. ওয়েব · ২. ইমেল (৩০s) · ৩. WhatsApp · ৪. শাখা · ৫. মোবাইল\nসঙ্গে সঙ্গে CMP-XXXXXXXX ID পাবেন।",
    register_what_needed:
      "প্রয়োজনীয়: কাস্টমার ID · সমস্যার বিবরণ · চ্যানেল · স্ক্রিনশট (ঐচ্ছিক)",
    how_pipeline:
      "**৯টি AI ধাপ:** PII → নকল পরীক্ষা → শ্রেণীবিভাগ → অনুভূতি → RBI → KB → সমাধান → তথ্য যাচাই → রাউটিং\nপ্রতিটি ধাপ স্বচ্ছ।",
    escalation_info:
      "Tier 0→1→2→3→4→5 (RBI Ombudsman)\nসর্বোচ্চ ৫ হপ। প্রতিটি স্তরে আপডেট।",
    channels_info: "ওয়েব · ইমেল · WhatsApp · শাখা · মোবাইল (সবই একই AI)",
    rbi_info: "ATM/UPI T+৫ দিনে ফেরত। TAT লঙ্ঘনে ₹১০০/দিন জরিমানা।",
    categories_info:
      "UPI · ATM · কার্ড · ঋণ · অ্যাকাউন্ট · KYC · বীমা · জালিয়াতি",
    track_info: "Complaint ID দিয়ে ড্যাশবোর্ড Complaints ট্যাবে খুঁজুন।",
    not_understood: "বুঝতে পারিনি। নিচের বিকল্পগুলি বেছে নিন।",
    followup: "আর কোনো সাহায্য দরকার?",
    goodbye: "ধন্যবাদ! 🙏 হেল্পলাইন: **1800 22 2244**",
  },

  Tamil: {
    greeting:
      "வணக்கம்! 👋 நான் **CustomerSetu** வழிகாட்டி.\nஃபிர்யாது பதிவு, கண்காணிப்பு மற்றும் புரிந்துகொள்வதில் உதவுவேன்.\n\nநீங்கள் என்ன விரும்புகிறீர்கள்?",
    menu_register: "📝 புகார் பதிவு",
    menu_track: "🔍 கண்காணிக்கவும்",
    menu_how: "🤖 AI எப்படி செயல்படுகிறது?",
    menu_escalate: "🔺 அதிகரிப்பு & உரிமைகள்",
    menu_channels: "📡 சேனல்கள்",
    menu_rbi: "⚖️ RBI விதிமுறைகள்",
    menu_categories: "📂 வகைகள்",
    menu_back: "⬅️ முதன்மை மெனு",
    register_intro:
      "**5 வழிகளில் புகார்:**\n1. வலை · 2. மின்னஞ்சல் (30s) · 3. WhatsApp · 4. கிளை · 5. மொபைல்\nCMP-XXXXXXXX ID உடனே கிடைக்கும்.",
    register_what_needed:
      "தேவையானவை: வாடிக்கையாளர் ID · சிக்கல் விளக்கம் · சேனல் · திரைப்பிடிப்பு (விருப்பமானது)",
    how_pipeline:
      "**9 AI படிகள்:** PII → நகல் → வகை → உணர்வு → RBI → KB → தீர்வு → உண்மை → வழிப்பாதை\nஒவ்வொரு படியும் வெளிப்படையானது.",
    escalation_info:
      "Tier 0→1→2→3→4→5 (RBI Ombudsman)\nமிகவும் 5 ஹாப்கள். ஒவ்வொரு நிலையிலும் புதுப்பிப்பு.",
    channels_info:
      "வலை · மின்னஞ்சல் · WhatsApp · கிளை · மொபைல் (அனைத்தும் ஒரே AI)",
    rbi_info:
      "ATM/UPI T+5 நாட்களில் திரும்பப்பெறுதல். TAT மீறலுக்கு ₹100/நாள்.",
    categories_info:
      "UPI · ATM · அட்டைகள் · கடன்கள் · கணக்குகள் · KYC · காப்பீடு · மோசடி",
    track_info: "Complaint ID மூலம் டாஷ்போர்டில் கண்காணிக்கவும்.",
    not_understood: "புரியவில்லை. கீழே உள்ள விருப்பங்களை தேர்ந்தெடுக்கவும்.",
    followup: "வேறு ஏதாவது உதவி?",
    goodbye: "நன்றி! 🙏 உதவி எண்: **1800 22 2244**",
  },

  Marathi: {
    greeting:
      "नमस्कार! 👋 मी **CustomerSetu** मार्गदर्शक.\nतक्रार नोंदवणे, ट्रॅक करणे आणि समजण्यात मदत करतो.\n\nआपल्याला काय हवे आहे?",
    menu_register: "📝 तक्रार नोंदवा",
    menu_track: "🔍 ट्रॅक करा",
    menu_how: "🤖 AI कसे काम करते?",
    menu_escalate: "🔺 एस्केलेशन व अधिकार",
    menu_channels: "📡 चॅनेल",
    menu_rbi: "⚖️ RBI नियम",
    menu_categories: "📂 श्रेण्या",
    menu_back: "⬅️ मुख्य मेनू",
    register_intro:
      "**5 मार्गांनी तक्रार:**\n1️⃣ वेब · 2️⃣ ईमेल (30s) · 3️⃣ WhatsApp · 4️⃣ शाखा · 5️⃣ मोबाइल\nCMP-XXXXXXXX ID लगेच मिळेल.",
    register_what_needed:
      "आवश्यक: ग्राहक ID · विषय वर्णन · चॅनेल · स्क्रीनशॉट (पर्यायी)",
    how_pipeline:
      "**9 AI चरण:** PII → डुप्लिकेट → वर्गीकरण → भावना → RBI → KB → निराकरण → तथ्य → रूटिंग\nप्रत्येक चरण पारदर्शक.",
    escalation_info:
      "Tier 0→1→2→3→4→5 (RBI Ombudsman)\nजास्तीत जास्त 5 हॉप्स. प्रत्येक टप्प्यावर अपडेट.",
    channels_info: "वेब · ईमेल · WhatsApp · शाखा · मोबाइल (सर्व एकाच AI वर)",
    rbi_info: "ATM/UPI T+5 दिवसांत परत. TAT उल्लंघनावर ₹100/दिवस.",
    categories_info: "UPI · ATM · कार्ड · कर्ज · खाती · KYC · विमा · फसवणूक",
    track_info: "Complaint ID ने डॅशबोर्ड Complaints टॅबमध्ये शोधा.",
    not_understood: "समजले नाही. खालील पर्याय निवडा.",
    followup: "आणखी काही मदत हवी का?",
    goodbye: "धन्यवाद! 🙏 हेल्पलाइन: **1800 22 2244**",
  },
};

// ── Helpers ───────────────────────────────────────────────────────────────────
function getLang(language: string): LangKey {
  const keys = Object.keys(T) as LangKey[];
  return keys.includes(language as LangKey) ? (language as LangKey) : "English";
}
function tr(lang: string, key: string): string {
  const l = getLang(lang);
  return T[l][key] ?? T["English"][key] ?? key;
}
function mainMenuOpts(lang: string): string[] {
  return [
    tr(lang, "menu_register"),
    tr(lang, "menu_track"),
    tr(lang, "menu_how"),
    tr(lang, "menu_escalate"),
    tr(lang, "menu_channels"),
    tr(lang, "menu_rbi"),
    tr(lang, "menu_categories"),
  ];
}

function getResponse(
  text: string,
  lang: string,
): { text: string; options?: string[] } {
  const s = text.toLowerCase();
  const back = [tr(lang, "menu_back")];

  if (
    /menu|main|start|help|hi\b|hello|hey|नमस्|నమస్|নমস্|வண|नमस्|back|⬅/.test(s)
  )
    return { text: tr(lang, "greeting"), options: mainMenuOpts(lang) };

  if (/register|new|submit|दर्ज|shikayat|నమోదు|নথি|பதிவு|नोंद/.test(s))
    return { text: tr(lang, "register_intro"), options: back };

  if (/info|need|what.*requir|क्या.*चाहिए/.test(s))
    return { text: tr(lang, "register_what_needed"), options: back };

  if (/track|status|cmp-|complaint id|ट्रैक|ट्रॅक|ट्रक/.test(s))
    return { text: tr(lang, "track_info"), options: back };

  if (/how|work|pipeline|process|ai|कैसे|ఎలా|কীভাবে|எப்படி|कसे/.test(s))
    return { text: tr(lang, "how_pipeline"), options: back };

  if (
    /escalat|tier|ombudsman|right|अधिकार|ఎస్కలేషన్|এস্কেলেশন|அதிகரிப்பு/.test(s)
  )
    return { text: tr(lang, "escalation_info"), options: back };

  if (/channel|whatsapp|email|branch|web|चैनल|ఛానెల్|চ্যানেল|சேனல்/.test(s))
    return { text: tr(lang, "channels_info"), options: back };

  if (/rbi|tat|guideline|penalty|जुर्माना|జరిమానా|জরিমানা|அபராதம்/.test(s))
    return { text: tr(lang, "rbi_info"), options: back };

  if (/categor|upi|atm|loan|card|account|fraud|kreditkarte/.test(s))
    return { text: tr(lang, "categories_info"), options: back };

  if (/yes|sure|हाँ|हां|అవును|হ্যাঁ|ஆம்|होय/.test(s))
    return { text: tr(lang, "followup"), options: mainMenuOpts(lang) };

  if (/no\b|done|bye|नहीं|లేదు|না|இல்லை|नाही/.test(s))
    return { text: tr(lang, "goodbye") };

  return { text: tr(lang, "not_understood"), options: mainMenuOpts(lang) };
}

// ── Render bold + newlines ─────────────────────────────────────────────────────
function renderMarkdown(text: string) {
  return text.split("\n").map((line, i, arr) => {
    const parts = line.split(/\*\*(.+?)\*\*/g);
    return (
      <React.Fragment key={i}>
        {parts.map((p, j) => (j % 2 === 1 ? <strong key={j}>{p}</strong> : p))}
        {i < arr.length - 1 && <br />}
      </React.Fragment>
    );
  });
}

const RuleBasedChatbot: React.FC<RuleBasedChatbotProps> = ({ language }) => {
  const [messages, setMessages] = useState<Message[]>([
    {
      sender: "bot",
      text: tr(language, "greeting"),
      options: mainMenuOpts(language),
    },
  ]);
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    setMessages([
      {
        sender: "bot",
        text: tr(language, "greeting"),
        options: mainMenuOpts(language),
      },
    ]);
  }, [language]);

  const send = (text: string) => {
    if (!text.trim()) return;
    const resp = getResponse(text, language);
    setMessages((prev) => [
      ...prev,
      { sender: "user", text },
      { sender: "bot", text: resp.text, options: resp.options },
    ]);
    setInput("");
  };

  return (
    /* Fill the remaining height from ChatbotWindow's flex body */
    <div className="flex flex-col h-full min-h-0">
      {/* ── Messages area — scrollable ── */}
      <div
        className="flex-1 overflow-y-auto px-3 py-3 space-y-3"
        style={{ background: "#f8fafc" }}
      >
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex items-end gap-1.5 ${msg.sender === "user" ? "flex-row-reverse" : "flex-row"}`}
          >
            {/* Avatar */}
            <div
              className="w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center text-sm"
              style={{
                background: msg.sender === "bot" ? "#1d4ed8" : "#e2e8f0",
                color: msg.sender === "bot" ? "#fff" : "#374151",
              }}
            >
              {msg.sender === "bot" ? "🤖" : "👤"}
            </div>

            <div style={{ maxWidth: "78%" }}>
              {/* Bubble */}
              <div
                className="px-3 py-2 rounded-2xl text-sm leading-relaxed"
                style={{
                  background: msg.sender === "bot" ? "#ffffff" : "#2563eb",
                  color: msg.sender === "bot" ? "#1e293b" : "#ffffff",
                  borderRadius:
                    msg.sender === "bot"
                      ? "4px 16px 16px 16px"
                      : "16px 4px 16px 16px",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
                  wordBreak: "break-word",
                }}
              >
                {renderMarkdown(msg.text)}
              </div>

              {/* Quick-reply chips */}
              {msg.sender === "bot" &&
                msg.options &&
                msg.options.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {msg.options.map((opt, oi) => (
                      <button
                        key={oi}
                        onClick={() => send(opt)}
                        className="text-xs px-2.5 py-1 rounded-full border transition-all duration-100 active:scale-95"
                        style={{
                          borderColor: "#bfdbfe",
                          background: "#eff6ff",
                          color: "#1d4ed8",
                          fontWeight: 500,
                        }}
                        onMouseEnter={(e) => {
                          (
                            e.currentTarget as HTMLButtonElement
                          ).style.background = "#dbeafe";
                        }}
                        onMouseLeave={(e) => {
                          (
                            e.currentTarget as HTMLButtonElement
                          ).style.background = "#eff6ff";
                        }}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* ── Input bar — pinned to bottom ── */}
      <div
        className="flex items-center gap-2 px-3 py-2 flex-shrink-0"
        style={{ borderTop: "1px solid #e2e8f0", background: "#ffffff" }}
      >
        <input
          className="flex-1 rounded-full px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          style={{ border: "1px solid #cbd5e1", background: "#f8fafc" }}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send(input)}
          placeholder={
            language === "Hindi"
              ? "संदेश लिखें…"
              : language === "Telugu"
                ? "సందేశం…"
                : language === "Bengali"
                  ? "বার্তা লিখুন…"
                  : language === "Tamil"
                    ? "செய்தி…"
                    : language === "Marathi"
                      ? "संदेश लिहा…"
                      : "Type a message…"
          }
        />
        <button
          onClick={() => send(input)}
          disabled={!input.trim()}
          className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 transition-all active:scale-95 disabled:opacity-40"
          style={{ background: "#2563eb" }}
          aria-label="Send"
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="white"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        </button>
      </div>
    </div>
  );
};

export default RuleBasedChatbot;
