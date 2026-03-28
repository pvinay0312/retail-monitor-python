"""All monitored product URLs / identifiers — SoleAlerts cook group edition.

Philosophy:
- Household consumables (Tide, paper towels, diapers, pet food, etc.) are
  intentionally omitted — the amazon_coupons.py spider auto-scans those.
- Focus: high-demand, resellable, hyped items across all stores.
- Pokemon TCG at Target/Walmart are CRITICAL — exclusive packs sell out in <60 s.
- RTX 5090 / 5080 are the hottest GPU drops right now (launched Jan 2025).
- PS5 Pro (Nov 2024) and Nintendo Switch 2 (2025) covered on every store.
"""

# ── Amazon ────────────────────────────────────────────────────────────────────
AMAZON_PRODUCTS = [

    # ── TVs ──────────────────────────────────────────────────────────────────
    "https://www.amazon.com/introducing-amazon-fire-tv-55-inch-omni-qled-series-smart-tv/dp/B09N6ZRH6C",
    "https://www.amazon.com/amazon-fire-tv-55-inch-omni-mini-led-series-smart-tv/dp/B0C7SRHGXF",
    "https://www.amazon.com/TCL-Class-QLED-Smart-Google/dp/B0B52PSLN4",
    "https://www.amazon.com/Hisense-Class-ULED-Mini-LED/dp/B0B4FD9TRP",
    "https://www.amazon.com/VIZIO-43-Inch-SmartCast-Television/dp/B09GSWLH9W",
    "https://www.amazon.com/Samsung-QN85B-Neo-QLED-Smart/dp/B09VB7VRTT",
    "https://www.amazon.com/LG-Class-OLED-Smart-TV/dp/B09MGLVJ4K",

    # ── Headphones ───────────────────────────────────────────────────────────
    "https://www.amazon.com/Sony-WH-1000XM5-Canceling-Headphones-Hands-Free/dp/B09XS7JWHH",
    "https://www.amazon.com/Sony-WH-1000XM5-Canceling-Headphones-Hands-Free/dp/B09XSDMT4F",
    "https://www.amazon.com/Bose-QuietComfort-45-Bluetooth-Canceling/dp/B098FKXT8L",
    "https://www.amazon.com/SteelSeries-Arctis-Nova-Gaming-Headset/dp/B09ZMYQ6P2",
    "https://www.amazon.com/Sony-WF-1000XM5-Canceling-Headphones/dp/B0C33XXS56",
    "https://www.amazon.com/Bose-QuietComfort-Earbuds-Wireless/dp/B08WM3GJ5Z",

    # ── AirPods / Apple Audio ─────────────────────────────────────────────────
    "https://www.amazon.com/Apple-Generation-Cancelling-Transparency-Personalized/dp/B0CHWRXH8B",
    "https://www.amazon.com/Apple-AirPods-Charging-Released-2019/dp/B07PXGQC1Q",
    "https://www.amazon.com/Apple-AirPods-Max-Wireless-Headphones/dp/B0CHX2DWWR",  # AirPods Max USB-C

    # ── Smartwatches ─────────────────────────────────────────────────────────
    "https://www.amazon.com/Apple-Watch-Smartwatch-Aluminium-Always/dp/B0DGHQ2QH6",
    "https://www.amazon.com/Apple-Watch-Smartwatch-Aluminium-Always/dp/B0DGJ5KQL7",

    # ── Speakers ─────────────────────────────────────────────────────────────
    "https://www.amazon.com/Amazon-vibrant-helpful-routines-Charcoal/dp/B09B8V1LZ3",
    "https://www.amazon.com/Amazon-release-vibrant-helpful-routines/dp/B09B94RL1R",
    "https://www.amazon.com/JBL-Flip-Waterproof-Bluetooth-Speaker/dp/B09XDB73CX",

    # ── Laptops / MacBooks ───────────────────────────────────────────────────
    "https://www.amazon.com/2022-Apple-MacBook-Laptop-chip/dp/B0B3BVWJ6Y",
    "https://www.amazon.com/Apple-2023-MacBook-Laptop-chip/dp/B0C7686169",
    "https://www.amazon.com/Apple-MacBook-Laptop-M4-chip/dp/B0DLGT6MCG",        # MacBook Air M4
    "https://www.amazon.com/Apple-MacBook-Pro-Laptop-M4/dp/B0DLGY7MFC",         # MacBook Pro M4
    "https://www.amazon.com/Lenovo-IdeaPad-Business-Processor-Storage/dp/B09TQXMM4P",
    "https://www.amazon.com/ASUS-VivoBook-Display-Fingerprint-Backlit/dp/B0BNJFH52H",
    "https://www.amazon.com/Acer-Aspire-Display-Backlit-Keyboard/dp/B0B4GYVNFY",
    "https://www.amazon.com/HP-Laptop-Intel-Core-i5/dp/B09TQXMF68",
    "https://www.amazon.com/Dell-XPS-Laptop-13-9315/dp/B0BLBLZ1MC",
    "https://www.amazon.com/Microsoft-Surface-Pro-Platinum-Device/dp/B0CMDXWVL6",

    # ── iPhone / Phones ──────────────────────────────────────────────────────
    "https://www.amazon.com/Apple-iPhone-16-Pro-Max/dp/B0DLHJ69VY",             # iPhone 16 Pro Max
    "https://www.amazon.com/Samsung-Galaxy-S23-Unlocked-Smartphone/dp/B0BLP2Y7TJ",
    "https://www.amazon.com/Samsung-Galaxy-S24-Ultra-Smartphone/dp/B0CMDWC436",
    "https://www.amazon.com/Google-Pixel-7a-Unlocked-Smartphone/dp/B0BZ9XNBRB",
    "https://www.amazon.com/Google-Pixel-8-Pro-Smartphone/dp/B0CGJ5JHF4",

    # ── Apple Vision Pro ─────────────────────────────────────────────────────
    "https://www.amazon.com/Apple-MR8H3LL-A-Vision-Pro/dp/B0CXFZQ4FB",

    # ── RTX 5000 Series GPUs (hottest resale items — launched Jan 2025) ──────
    "https://www.amazon.com/ASUS-Graphics-3-8-Slot-Axial-tech-Phase-Change/dp/B0DS2WQZ2M",  # ASUS ROG Astral RTX 5090 OC
    "https://www.amazon.com/MSI-GeForce-5090-Gaming-Trio/dp/B0DT6Q3BXM",                  # MSI RTX 5090 Gaming Trio OC
    "https://www.amazon.com/ASUS-Graphics-3-8-Slot-Axial-tech-Phase-Change/dp/B0DQSD7YQC", # ASUS ROG Astral RTX 5080 OC
    "https://www.amazon.com/GIGABYTE-Graphics-WINDFORCE-GV-N5080GAMING-OC-16GD/dp/B0DS2R6948", # Gigabyte RTX 5080 Gaming OC
    # RTX 40-series (still highly liquid)
    "https://www.amazon.com/ASUS-GeForce-DisplayPort-Axial-tech-Technology/dp/B0CNBGFQWG",
    "https://www.amazon.com/MSI-RTX-4070-GAMING-16G/dp/B0CNQKSFXR",

    # ── Gaming Consoles ──────────────────────────────────────────────────────
    "https://www.amazon.com/PlayStation-5-Console-CFI-2015A01X/dp/B0CL5KNB9M",
    "https://www.amazon.com/PlayStation-5-Pro-Console/dp/B0CZG7H7XX",           # PS5 Pro
    "https://www.amazon.com/Nintendo-Switch-OLED-Model-Neon-Joy/dp/B098RL6SBJ",
    "https://www.amazon.com/Nintendo-Switch-OLED-Model-White-Joy/dp/B098BKLHBJ",
    "https://www.amazon.com/dp/B0F3GWXLTS",                                     # Nintendo Switch 2
    "https://www.amazon.com/Xbox-Series-S-Robot-White/dp/B08G9J44ZN",

    # ── Gaming Controllers / Peripherals ─────────────────────────────────────
    "https://www.amazon.com/DualSense-Wireless-Controller-PlayStation-5/dp/B08H99BPJN",
    "https://www.amazon.com/Nintendo-Switch-Pro-Controller/dp/B01NAWKPOF",
    "https://www.amazon.com/Xbox-Wireless-Controller-Carbon-Black/dp/B08DF26MLL",
    "https://www.amazon.com/Backbone-One-Mobile-Gaming-Controller/dp/B09BTZX5MK",
    "https://www.amazon.com/Logitech-Performance-Gaming-Mouse-Programmable/dp/B07GBZ4Q68",
    "https://www.amazon.com/Razer-DeathAdder-Essential-Gaming-Mouse/dp/B07FRLXG58",
    "https://www.amazon.com/HyperX-Alloy-FPS-Mechanical-Gaming/dp/B019PIXO76",
    "https://www.amazon.com/SteelSeries-Arctis-Nova-Pro-Wireless/dp/B09ZMYBSZP",
    "https://www.amazon.com/Turtle-Beach-Stealth-Gaming-Headset/dp/B09WFKWC2F",

    # ── Pokemon TCG (booster boxes resell 2–4× on release week) ─────────────
    "https://www.amazon.com/dp/B0DG9NFTLJ",   # Pokemon TCG Prismatic Evolutions ETB
    "https://www.amazon.com/dp/B0BPZFB8R2",   # Pokemon TCG 151 Ultra Premium Collection
    "https://www.amazon.com/dp/B0CHW6LZ7T",   # Pokemon Scarlet Violet Booster Bundle
    "https://www.amazon.com/dp/B0CVJM31VJ",   # Pokemon Temporal Forces Elite Trainer Box

    # ── LEGO Exclusives (Icons, Technic, Star Wars) ──────────────────────────
    "https://www.amazon.com/LEGO-Icons-Eiffel-Tower-10307/dp/B0BFJ11DXN",
    "https://www.amazon.com/LEGO-Technic-Bugatti-Bolide-42151/dp/B0BF3V2T8P",
    "https://www.amazon.com/LEGO-Icons-Wildflower-Bouquet-10313/dp/B09JWST8KX",
    "https://www.amazon.com/LEGO-Icons-Succulents-10309/dp/B09JWTD7PQ",
    "https://www.amazon.com/LEGO-Star-Wars-Millennium-75375/dp/B0CQTW7RDZ",

    # ── Sneakers on Amazon (discount/restock potential) ───────────────────────
    "https://www.amazon.com/Nike-FB2207-Mens-Running-Shoe/dp/B0DHQ467TR",
    "https://www.amazon.com/Nike-Experience-Running-Trainers-Sneakers/dp/B0BLW6SVJ7",
    "https://www.amazon.com/Nike-Jordan-Retro-Mens/dp/B0BXZLKKBB",
    "https://www.amazon.com/adidas-Originals-Ultraboost-Running-Shoes/dp/B0B5C1PKHV",
    "https://www.amazon.com/New-Balance-Fresh-Foam-Running/dp/B0B8WLFZ3D",
    "https://www.amazon.com/New-Era-Yankees-59FIFTY-Fitted/dp/B07J8MKRS3",

    # ── Tablets ──────────────────────────────────────────────────────────────
    "https://www.amazon.com/Amazon-Fire-HD-10-tablet/dp/B08F5MK6VB",
    "https://www.amazon.com/Amazon-Fire-Max-11-tablet/dp/B0B1VQ1ZQY",
    "https://www.amazon.com/Samsung-Galaxy-Tab-A8-SM-X200NZAAXAR/dp/B09N9HWSHY",
    "https://www.amazon.com/Apple-2022-iPad-Wi-Fi-64GB/dp/B0BJLXMVTM",

    # ── Kindle ───────────────────────────────────────────────────────────────
    "https://www.amazon.com/Kindle-Paperwhite-adjustable-warm-light/dp/B09TMF6742",

    # ── Accessories — Chargers, Cables, MagSafe ──────────────────────────────
    "https://www.amazon.com/Anker-Portable-PowerCore-Capacity-Compatible/dp/B0C6XRXB5N",
    "https://www.amazon.com/Anker-Charging-Foldable-Compatible-Included/dp/B09W2PNLX4",
    "https://www.amazon.com/Anker-Nano-Charger-Foldable-PowerIQ/dp/B08LH2KBQ2",
    "https://www.amazon.com/AmazonBasics-High-Speed-HDMI-Cable/dp/B014I8SSD0",
    "https://www.amazon.com/Anker-Magnetic-Wireless-Foldable-Charging/dp/B09K3WQ2QD",
    "https://www.amazon.com/Anker-Certified-Lightning-Compatible-AirPods/dp/B07K97LWRN",
    "https://www.amazon.com/Anker-PowerExpand-Aluminum-Thunderbolt-Charging/dp/B08C9HZ6Y6",
    "https://www.amazon.com/uni-USB-C-Hub-Adapter/dp/B075XNWRQX",

    # ── Phone Cases ──────────────────────────────────────────────────────────
    "https://www.amazon.com/Spigen-Rugged-Armor-Designed-iPhone/dp/B0CKWN5K66",
    "https://www.amazon.com/TORRAS-Compatible-iPhone-15-Case/dp/B0C7GP2Q3D",
    "https://www.amazon.com/Mophie-juice-pack-Wireless-Compatible/dp/B09Y26QK3H",
    "https://www.amazon.com/PopSockets-PopGrip-Swappable-Phones-Tablets/dp/B075YG3931",

    # ── Storage — SD Cards / Flash ────────────────────────────────────────────
    "https://www.amazon.com/SanDisk-Ultra-MicroSDXC-Memory-Adapter/dp/B08GY9NYRM",
    "https://www.amazon.com/Samsung-MicroSDXC-Memory-Adapter-MB-ME256KA/dp/B09B1J5PJN",

    # ── Smart Home ───────────────────────────────────────────────────────────
    "https://www.amazon.com/Ring-Video-Doorbell-1080p-Satin/dp/B08N5NQ869",
    "https://www.amazon.com/Wyze-Cam-Indoor-Wireless-Detection/dp/B076H3SRXG",
    "https://www.amazon.com/Kasa-Smart-Plug-Ultra-Mini/dp/B08LN3C7WK",
    "https://www.amazon.com/Govee-Smart-Light-Bulbs-Works/dp/B09L5JFMMD",
    "https://www.amazon.com/Govee-RGBIC-Smart-LED-Strip/dp/B09NQTJ5JV",
    "https://www.amazon.com/Philips-Hue-Brilliance-Starter-Compatible/dp/B07GFCN3WK",
    "https://www.amazon.com/ecobee-SmartThermostat-Premium-built-in/dp/B09XXS48P8",
    "https://www.amazon.com/Yale-Assure-Touchscreen-Deadbolt-YRD226/dp/B07NRHKP87",
    "https://www.amazon.com/Arlo-Pro-Security-Camera-VMC4050P/dp/B07HGJCZQR",
    "https://www.amazon.com/Blink-Outdoor-4th-Gen-security/dp/B0B1N5HW22",
    "https://www.amazon.com/TP-Link-Tapo-Security-Camera/dp/B08HJKTN8Z",
    "https://www.amazon.com/Google-Nest-Hub-2nd-Gen/dp/B08XMFKF47",

    # ── Security Cameras ─────────────────────────────────────────────────────
    "https://www.amazon.com/Wyze-Cam-v3-Color-Night/dp/B08MQZXSFC",
    "https://www.amazon.com/Ring-Stick-Up-Cam-Battery/dp/B07ZQ66TL3",
    "https://www.amazon.com/Eufy-Security-Detection-Compatible-Assistant/dp/B086XHG94X",

    # ── Kitchen ───────────────────────────────────────────────────────────────
    "https://www.amazon.com/Ninja-AF101-Air-Fryer-Crisps/dp/B07FDJMC9Q",
    "https://www.amazon.com/COSORI-Air-Fryer-Oven-Combination/dp/B0974C3QTN",
    "https://www.amazon.com/Instant-Pot-Multi-Use-Programmable-Pressure/dp/B00FLYWNYQ",
    "https://www.amazon.com/Instant-Electric-Multicooker-Dehydrates-Stainless/dp/B07VT23JDM",
    "https://www.amazon.com/Ninja-Creami-Deluxe-Milkshake-NC501/dp/B0B8HB85QP",
    "https://www.amazon.com/Keurig-K-Slim-Single-Serve-K-Cup/dp/B07GV2S1GS",
    "https://www.amazon.com/Keurig-K-Duo-Coffee-Maker/dp/B07ST3W2JT",
    "https://www.amazon.com/Nespresso-Vertuo-Pop-Coffee-Espresso/dp/B0BLTWK7Z5",
    "https://www.amazon.com/Breville-BJE830BSS-Juice-Fountain-Cold-XL/dp/B07DQXM6RL",
    "https://www.amazon.com/Vitamix-5200-Blender-Black-Standard/dp/B008H4SLV6",
    "https://www.amazon.com/Cuisinart-CBK-110P1-Compact-Automatic-Breadmaker/dp/B0000Y3MHA",
    "https://www.amazon.com/KitchenAid-KSM150PSER-Artisan-Tilt-Head-Stand/dp/B00005UP2P",
    "https://www.amazon.com/Instant-Pot-Duo-Crisp-11-in-1/dp/B07W55LHPK",
    "https://www.amazon.com/Ninja-BL770-Blender-Processing-Smoothies/dp/B00NGV4506",
    "https://www.amazon.com/Crock-Pot-SCV700SS-7-Quart-Stainless/dp/B000G0I0E2",
    "https://www.amazon.com/Chefman-TurboFry-Space-Saving-Rotisserie/dp/B08HJZS1RK",

    # ── Vacuums ──────────────────────────────────────────────────────────────
    "https://www.amazon.com/iRobot-Vacuum-Wi-Fi-Connectivity-Carpets-Self-Charging/dp/B08SP5GYJP",
    "https://www.amazon.com/iRobot-Roomba-Self-Emptying-Robot-Vacuum/dp/B0C415NHBM",

    # ── Fitness (high-end) ────────────────────────────────────────────────────
    "https://www.amazon.com/Bowflex-SelectTech-Adjustable-Dumbbell-Version/dp/B001ARYS0A",
    "https://www.amazon.com/Yes4All-Solid-Kettlebell-Weight/dp/B00CBZUUOU",
    "https://www.amazon.com/Garmin-Forerunner-Smartwatch-Advanced/dp/B0B41QBKRD",
    "https://www.amazon.com/Fitbit-Advanced-Tracker-Health-Monitoring/dp/B0BJWJWSVC",
    "https://www.amazon.com/Withings-Body-Smart-Advanced-Composition/dp/B0CF8DK4KK",
    "https://www.amazon.com/Omron-Evolv-Wireless-Monitor-BP7350/dp/B07CC6FMFT",
    "https://www.amazon.com/RENPHO-Smart-Scale-Bluetooth-Composition/dp/B01N1UX8RW",

    # ── Monitors & Displays ───────────────────────────────────────────────────
    "https://www.amazon.com/LG-27GL83A-B-Ultragear-Compatible-Response/dp/B07XTLW1X7",
    "https://www.amazon.com/Samsung-Odyssey-FreeSync-Monitor-LC27G55T/dp/B08G3MCHMJ",
    "https://www.amazon.com/Dell-S2722DGM-Curved-Gaming-Monitor/dp/B095WCQN7T",
    "https://www.amazon.com/ASUS-1080P-Monitor-VG248QG-FreeSync/dp/B07H93TK3T",
    "https://www.amazon.com/Acer-SB220Q-Ultra-Thin-Frame-Monitor/dp/B07CVL2D2S",

    # ── Cameras & Drones ─────────────────────────────────────────────────────
    "https://www.amazon.com/DJI-Mini-4-Pro-Drone/dp/B0CF9GQMJP",
    "https://www.amazon.com/GoPro-HERO12-Black-Waterproof-Stabilization/dp/B0CDP3XGHQ",
    "https://www.amazon.com/Canon-EOS-Rebel-SL3-Video/dp/B07MV3P7M8",
    "https://www.amazon.com/Sony-Full-Frame-Mirrorless-Interchangeable/dp/B09BBGPTLG",
    "https://www.amazon.com/Fujifilm-X-T30-II-Body-Silver/dp/B09GBC3B9B",

    # ── Projectors ────────────────────────────────────────────────────────────
    "https://www.amazon.com/XGIMI-Projector-Android-Harman-Kardon/dp/B09DMTGWL8",
    "https://www.amazon.com/Anker-Nebula-Capsule-Android-Projector/dp/B08LWSJ1V4",
    "https://www.amazon.com/Epson-EpiqVision-Mini-EF12-Streaming/dp/B091TGTHWG",

    # ── Streaming Devices ─────────────────────────────────────────────────────
    "https://www.amazon.com/Introducing-Amazon-Fire-Stick-with-Alexa/dp/B0BTXZWF3K",
    "https://www.amazon.com/Google-Chromecast-with-Google-TV/dp/B08KRV7S22",
    "https://www.amazon.com/Roku-Streaming-Stick-Plus-Streaming/dp/B075XN5L53",
    "https://www.amazon.com/Apple-TV-4K-Wi-Fi/dp/B09JCDG2JP",

    # ── Portable Power ────────────────────────────────────────────────────────
    "https://www.amazon.com/Jackery-Portable-Explorer-Generator-Emergency/dp/B082TMBYR6",
    "https://www.amazon.com/EcoFlow-Portable-Generator-Emergency-Charging/dp/B0CG5PQB7T",

    # ── Stanley / Viral Drinkware ─────────────────────────────────────────────
    "https://www.amazon.com/Stanley-Quencher-FlowState-Tumbler-Meadow/dp/B0CJHQHPPF",
    "https://www.amazon.com/Stanley-Quencher-FlowState-Stainless-Dishwasher/dp/B09JQMJHXY",

    # ── Tools & Home Improvement ──────────────────────────────────────────────
    "https://www.amazon.com/DEWALT-Cordless-Drill-Compact-DCD771C2/dp/B00ET4N2EY",
    "https://www.amazon.com/BLACK-DECKER-Cordless-Drill-LDX120C/dp/B004OFW51O",
    "https://www.amazon.com/CRAFTSMAN-Mechanics-Tool-Set-99-Piece/dp/B07WRRJR55",
    "https://www.amazon.com/Makita-XPH12Z-Brushless-Cordless-Hammer/dp/B07NFNG5MZ",
    "https://www.amazon.com/WD-40-Multi-Use-Product-Smart-Straw/dp/B0006IBQXQ",
    "https://www.amazon.com/MILWAUKEE-2606-22CT-M18-Compact-Drill/dp/B07PMXPL86",
    "https://www.amazon.com/Stanley-STHT77588-Measuring-Tape/dp/B003MC3KGC",

    # ── Car Accessories ───────────────────────────────────────────────────────
    "https://www.amazon.com/Anker-Roav-DashCam-Nighthawk-Stabilization/dp/B06XSVTJQP",
    "https://www.amazon.com/NOCO-Boost-Plus-GB40-1000Amp/dp/B015TKUPIC",
    "https://www.amazon.com/Garmin-DriveSmart-Bluetooth-Optional/dp/B07R7K9TH2",
    "https://www.amazon.com/VIOFO-A119-MINI-2-Dash-Cam/dp/B09FJBKXNL",
    "https://www.amazon.com/Car-Phone-Mount-Holder-Dashboard/dp/B08FQTKXSX",
    "https://www.amazon.com/Chemical-Guys-CWS_301_16-Extreme-Cleanser/dp/B00FMJNGK6",
    "https://www.amazon.com/Meguiars-G7014J-Gold-Class-Carnauba/dp/B0000AY0KX",

    # ── Air Purifiers / Home Climate ──────────────────────────────────────────
    "https://www.amazon.com/LEVOIT-Purifiers-Cleaner-Filtration-Eliminators/dp/B07D8TQN68",
    "https://www.amazon.com/Honeywell-HPA300-True-HEPA-Allergen/dp/B00GS0U5CG",
    "https://www.amazon.com/LEVOIT-Humidifiers-Bedroom-Cool-Mist/dp/B07L5SSHRD",
    "https://www.amazon.com/Vornado-660-Large-Whole-Room/dp/B0034DGN4E",
    "https://www.amazon.com/Dyson-Purifier-Cool-Gen1-DP10/dp/B0CJVGJLRC",

    # ── Office / Desk Setup ───────────────────────────────────────────────────
    "https://www.amazon.com/AmazonBasics-Ergonomic-Adjustable-Computer-Chair/dp/B073ZVZQ6Z",
    "https://www.amazon.com/Logitech-MX-Master-Wireless-Mouse/dp/B07S395RWD",
    "https://www.amazon.com/HP-LaserJet-Printer-M209dwe-Works/dp/B09C3XTMKP",
    "https://www.amazon.com/Canon-PIXMA-Wireless-Printer-Printing/dp/B09BQZJZPH",
    "https://www.amazon.com/Epson-EcoTank-ET-2803-Cartridge-Free/dp/B09CRVD48C",
    "https://www.amazon.com/Anker-PowerConf-Bluetooth-Speakerphone/dp/B07QCS2SZP",
    "https://www.amazon.com/Logitech-C920x-Pro-Webcam-Recording/dp/B085TFF7M1",
    "https://www.amazon.com/Elgato-Stream-Deck-Controller-Customizable/dp/B06XKNZT1P",

    # ── Skincare (high-value items only) ──────────────────────────────────────
    "https://www.amazon.com/CeraVe-Hyaluronic-Ceramides-Niacinamide-Non-Drying/dp/B07RJ18VMF",
    "https://www.amazon.com/Neutrogena-Moisturizer-Retinol-Hyaluronic-Sunscreen/dp/B0081E6YX4",

    # ── Personal Care Devices ─────────────────────────────────────────────────
    "https://www.amazon.com/Oral-B-1000-Rechargeable-Electric-Toothbrush/dp/B003UKM9CO",
    "https://www.amazon.com/Gillette-Fusion5-Razor-Blade-Refills/dp/B01N5TCKZF",

    # ── Home Décor / Bedding ──────────────────────────────────────────────────
    "https://www.amazon.com/Beckham-Hotel-Collection-Gel-Pillows/dp/B01LYNW421",
    "https://www.amazon.com/SLEEP-ZONE-Cooling-Comforter-Machine/dp/B08CJKD8LZ",
    "https://www.amazon.com/Amazon-Basics-Lightweight-Microfiber-Sheet/dp/B0777YMY89",
    "https://www.amazon.com/Mellanni-Bed-Sheet-Set-Full/dp/B01IB09K7Y",
    "https://www.amazon.com/TOPRUUG-Washable-Oriental-Area-Rug/dp/B0CFY66MZG",
    "https://www.amazon.com/Utopia-Towels-Luxurious-Absorbent-Perfect/dp/B07SW4HB3N",

    # ── Furniture ─────────────────────────────────────────────────────────────
    "https://www.amazon.com/Flash-Furniture-Adjustable-Ergonomic-Swivel/dp/B08BFNRM4N",
    "https://www.amazon.com/Hbada-Ergonomic-Office-Chair-Support/dp/B07SDMFCH2",
    "https://www.amazon.com/SONGMICS-Storage-Ottoman-Footstool-ULSF002/dp/B06XGJ2GGN",
    "https://www.amazon.com/Christopher-Knight-Home-Accent-Chair/dp/B07BFHF14N",
    "https://www.amazon.com/Zinus-Oluwafemi-Upholstered-Platform-Mattress/dp/B072BSTNCY",

    # ── Board Games & Collectibles ────────────────────────────────────────────
    "https://www.amazon.com/Catan-Board-Game/dp/B00U26V4VQ",
    "https://www.amazon.com/Ticket-Ride-Strategy-Board-Game/dp/B000BW7FKY",
    "https://www.amazon.com/Codenames-Strategy-Party-Card-Game/dp/B014Q1XX9S",
    "https://www.amazon.com/Hasbro-Monopoly-Classic-Game/dp/B00SIVLTM4",
    "https://www.amazon.com/Jenga-Game-54-Hardwood-Blocks/dp/B078Q1D5JR",

    # ── Outdoor & Patio ───────────────────────────────────────────────────────
    "https://www.amazon.com/Coleman-Portable-Camping-Chair-Arm/dp/B000ARPS5A",
    "https://www.amazon.com/TIMBER-RIDGE-Zero-Gravity-Recliner/dp/B01A4YQM3G",
    "https://www.amazon.com/Weber-Spirit-II-E-310-Liquid/dp/B074B3PRYN",
    "https://www.amazon.com/Solo-Stove-Bonfire-Lightweight-Portable/dp/B09GR7NJWL",
    "https://www.amazon.com/Outsunny-Umbrella-Patio-Cantilever-Hanging/dp/B09CDQHVQR",
    "https://www.amazon.com/EVER-ADVANCED-Lightweight-Outdoor-Breathable/dp/B07PHXFHRF",

    # ── Luggage & Travel ──────────────────────────────────────────────────────
    "https://www.amazon.com/AmazonBasics-Hardside-Spinner-Luggage-Black/dp/B07X8QLPT1",
    "https://www.amazon.com/Travelpro-Maxlite-Lightweight-Expandable-Suitcase/dp/B07R4JZZM4",
    "https://www.amazon.com/Samsonite-Omni-PC-Hardside-Spinner/dp/B009WBDPYU",
    "https://www.amazon.com/BAGSMART-Electronic-Organizer-Universal-Accessories/dp/B074W94QBJ",
    "https://www.amazon.com/AmazonBasics-Packing-Travel-Cubes-Set/dp/B014VBGBER",

    # ── Sports & Outdoors ─────────────────────────────────────────────────────
    "https://www.amazon.com/Intex-Explorer-K2-Kayak-Person/dp/B002IXNXXY",
    "https://www.amazon.com/Wilson-Adult-Recreational-Tennis-Racket/dp/B008G8BPRW",
    "https://www.amazon.com/Spalding-NBA-Varsity-Outdoor-Basketball/dp/B07WNWJCQJ",
    "https://www.amazon.com/Franklin-Sports-Pickleball-Paddle-Balls/dp/B07MK9LBHZ",
    "https://www.amazon.com/Callaway-Strata-Complete-Golf-Set/dp/B007Q3JQA4",
    "https://www.amazon.com/HEAD-Ti-S6-Racquets/dp/B000BT01BG",

    # ── Electric Bikes & Scooters ─────────────────────────────────────────────
    "https://www.amazon.com/Lectric-XP-Trike-Electric-Bike/dp/B0BTTQPG76",
    "https://www.amazon.com/Razor-E300-Electric-Scooter-Black/dp/B000BGJPNW",
    "https://www.amazon.com/Segway-Ninebot-Electric-Kick-Scooter/dp/B07K7XCLPD",
    "https://www.amazon.com/Gotrax-GXL-V2-Commuting-Electric/dp/B07J7MNKGZ",
    "https://www.amazon.com/Hiboy-S2-Electric-Scooter-Adults/dp/B07YQLM1X9",

    # ── Gardening ─────────────────────────────────────────────────────────────
    "https://www.amazon.com/Fiskars-Bypass-Pruning-Shears-Gardening/dp/B00004SD5U",
    "https://www.amazon.com/Garden-Hose-Expandable-50ft/dp/B078WGVGKY",
    "https://www.amazon.com/Miracle-Gro-Performance-Organics-Purpose/dp/B07BKCZR2N",
    "https://www.amazon.com/Scotts-Turf-Builder-Lawn-Food/dp/B000N4FKQG",
    "https://www.amazon.com/VIVOSUN-Hydroponic-Grow-Tent-Mylar/dp/B075BWFGKZ",
    "https://www.amazon.com/Rain-Bird-ST8I-WiFi-Smart-Irrigation/dp/B07BGYX2TZ",
    "https://www.amazon.com/Keter-Cortina-Outdoor-Storage-Resin/dp/B09Q4YFZTT",

    # ── Health & Wellness Devices ─────────────────────────────────────────────
    "https://www.amazon.com/Fitbit-Advanced-Tracker-Health-Monitoring/dp/B0BJWJWSVC",

]

# ── Best Buy ──────────────────────────────────────────────────────────────────
BESTBUY_PRODUCTS = [

    # ── Gaming Consoles ───────────────────────────────────────────────────────
    "https://www.bestbuy.com/site/sony-playstation-5-console/6523167.p",
    "https://www.bestbuy.com/site/sony-playstation-5-digital-edition-console/6523168.p",
    "https://www.bestbuy.com/site/sony-playstation-5-pro-console/6583138.p",             # PS5 Pro
    "https://www.bestbuy.com/site/microsoft-xbox-series-x-1tb-console/6428324.p",
    "https://www.bestbuy.com/site/nintendo-switch-oled-model-with-white-joy-con/6470924.p",
    "https://www.bestbuy.com/site/nintendo-switch-oled-model-w-neon-red-neon-blue-joy-con/6470925.p",
    "https://www.bestbuy.com/site/nintendo-switch-2/6614313.p",
    "https://www.bestbuy.com/site/meta-quest-3-128gb/6531587.p",
    "https://www.bestbuy.com/site/meta-quest-3s-128gb/6570888.p",

    # ── RTX 5090 / 5080 GPUs (most in-demand drops) ───────────────────────────
    "https://www.bestbuy.com/site/nvidia-geforce-rtx-5090-founders-edition/6614151.p",
    "https://www.bestbuy.com/site/nvidia-geforce-rtx-5080-founders-edition/6614153.p",
    "https://www.bestbuy.com/site/asus-rog-strix-geforce-rtx-5090/6614120.p",
    "https://www.bestbuy.com/site/msi-geforce-rtx-5090-gaming-x-trio/6616090.p",
    # RTX 40-series (still active market)
    "https://www.bestbuy.com/site/nvidia-geforce-rtx-4080-super-16gb-gddr6x/6570550.p",
    "https://www.bestbuy.com/site/nvidia-geforce-rtx-4070-super-12gb-gddr6x/6570551.p",
    "https://www.bestbuy.com/site/asus-geforce-rtx-4070-ti-super-16gb/6570315.p",

    # ── Pokemon TCG (Best Buy carries these — sell out fast) ──────────────────
    "https://www.bestbuy.com/site/pokemon-prismatic-evolutions-elite-trainer-box/6606082.p",

    # ── LEGO Exclusives ───────────────────────────────────────────────────────
    "https://www.bestbuy.com/site/lego-technic-bugatti-bolide-42151/6529527.p",

    # ── Apple ─────────────────────────────────────────────────────────────────
    "https://www.bestbuy.com/site/apple-airpods-pro-2nd-generation-with-magsafe-case-usb%E2%80%91c/6447382.p",
    "https://www.bestbuy.com/site/apple-airpods-4th-generation/6578852.p",
    "https://www.bestbuy.com/site/apple-airpods-max-usb-c/6578545.p",
    "https://www.bestbuy.com/site/apple-watch-series-10-gps-42mm-aluminum-case/6593286.p",
    "https://www.bestbuy.com/site/apple-macbook-air-13-inch-laptop-apple-m3-chip-8gb-memory-256gb/6565837.p",
    "https://www.bestbuy.com/site/apple-macbook-pro-14-inch-laptop-apple-m4-pro/6578533.p",
    "https://www.bestbuy.com/site/apple-ipad-10th-generation-10-9-inch-64gb-wi-fi/6499637.p",
    "https://www.bestbuy.com/site/apple-iphone-16-pro-max-512gb-natural-titanium/6443380.p",

    # ── Headphones ────────────────────────────────────────────────────────────
    "https://www.bestbuy.com/site/sony-wh-1000xm5-wireless-noise-canceling-over-ear-headphones/6505727.p",
    "https://www.bestbuy.com/site/bose-quietcomfort-45-wireless-noise-cancelling-over-ear-headphones/6471291.p",
    "https://www.bestbuy.com/site/samsung-galaxy-buds-fe-true-wireless-earbud-headphones/6543680.p",

    # ── TVs ───────────────────────────────────────────────────────────────────
    "https://www.bestbuy.com/site/samsung-65-class-the-frame-qled-4k-smart-tv/6401722.p",
    "https://www.bestbuy.com/site/lg-55-class-c3-series-oled-evo-4k-uhd-smart-webos-tv/6535928.p",
    "https://www.bestbuy.com/site/tcl-55-class-q6-qled-4k-smart-google-tv/6543914.p",

    # ── Smart Home ────────────────────────────────────────────────────────────
    "https://www.bestbuy.com/site/amazon-echo-dot-5th-gen-2022-release/6518518.p",
    "https://www.bestbuy.com/site/google-nest-thermostat/6429775.p",
    "https://www.bestbuy.com/site/ring-video-doorbell-wired/6427709.p",

    # ── Laptops ───────────────────────────────────────────────────────────────
    "https://www.bestbuy.com/site/lenovo-ideapad-flex-5i-14-fhd-touch-2-in-1-laptop/6584291.p",
    "https://www.bestbuy.com/site/hp-15-6-laptop-intel-core-i5-8gb-memory/6546563.p",

    # ── Appliances ────────────────────────────────────────────────────────────
    "https://www.bestbuy.com/site/dyson-v8-cordless-vacuum/6545258.p",
    "https://www.bestbuy.com/site/instant-pot-duo-7-in-1-electric-pressure-cooker-6-quart/6494977.p",

    # ── Gaming Accessories ────────────────────────────────────────────────────
    "https://www.bestbuy.com/site/xbox-wireless-controller-carbon-black/6430655.p",
    "https://www.bestbuy.com/site/steelseries-arctis-nova-pro-wireless-gaming-headset/6502647.p",
    "https://www.bestbuy.com/site/razer-blackshark-v2-pro-wireless-gaming-headset/6457401.p",
    "https://www.bestbuy.com/site/nintendo-switch-pro-controller/6080398.p",

    # ── Electric Bikes & Scooters ─────────────────────────────────────────────
    "https://www.bestbuy.com/site/segway-ninebot-kickscooter-e2-plus/6507490.p",
    "https://www.bestbuy.com/site/rad-power-bikes-radrunner-3-plus-electric-utility-bike/6571234.p",

    # ── Monitors & Displays ───────────────────────────────────────────────────
    "https://www.bestbuy.com/site/lg-27-class-ultragear-qhd-ips-1ms-165hz-gaming-monitor/6524201.p",
    "https://www.bestbuy.com/site/samsung-27-odyssey-g5-gaming-monitor/6401570.p",
    "https://www.bestbuy.com/site/dell-27-gaming-monitor-s2722dgm/6457707.p",

    # ── Cameras & Drones ──────────────────────────────────────────────────────
    "https://www.bestbuy.com/site/dji-mini-4-pro-fly-more-combo-drone/6560191.p",
    "https://www.bestbuy.com/site/gopro-hero12-black/6548994.p",

    # ── Furniture & Home Office ───────────────────────────────────────────────
    "https://www.bestbuy.com/site/insignia-adjustable-standing-desk/6502328.p",
    "https://www.bestbuy.com/site/ergotron-lx-desk-mount-lcd-monitor-arm/4890920.p",

]

# ── Walmart ───────────────────────────────────────────────────────────────────
WALMART_PRODUCTS = [

    # ── Pokemon TCG Walmart Exclusives (sell out FASTEST at Walmart) ──────────
    "https://www.walmart.com/ip/Pokemon-Prismatic-Evolutions-Elite-Trainer-Box/13816151308",
    "https://www.walmart.com/ip/Pokemon-TCG-151-Ultra-Premium-Collection/3606845180",

    # ── Funko Pop Exclusives ──────────────────────────────────────────────────
    "https://www.walmart.com/ip/Funko-Pop-Dragon-Ball-Super-Zamasu/153254915",

    # ── Gaming Consoles ───────────────────────────────────────────────────────
    "https://www.walmart.com/ip/PlayStation-5-Console/363472942",
    "https://www.walmart.com/ip/PlayStation-5-Digital-Edition-Console/1736740710",
    "https://www.walmart.com/ip/PlayStation-5-Pro-Console/18235967161",
    "https://www.walmart.com/ip/Nintendo-Switch-OLED-Model-w-Neon-Red-Neon-Blue-Joy-Con/910582148",
    "https://www.walmart.com/ip/Nintendo-Switch-OLED-Model-w-White-Joy-Con/493454737",
    "https://www.walmart.com/ip/Nintendo-Switch-2/15949610846",
    "https://www.walmart.com/ip/Nintendo-Switch-Pro-Controller/319026465",
    "https://www.walmart.com/ip/Xbox-Series-X-Console/443574645",
    "https://www.walmart.com/ip/Xbox-Series-S-512GB-All-Digital-Console/408062341",
    "https://www.walmart.com/ip/DualSense-Wireless-Controller-PlayStation-5/680339246",
    "https://www.walmart.com/ip/Meta-Quest-2-128GB-Advanced-VR-Headset/521108397",

    # ── LEGO ─────────────────────────────────────────────────────────────────
    "https://www.walmart.com/ip/LEGO-Icons-Eiffel-Tower/3792956367",
    "https://www.walmart.com/ip/LEGO-Star-Wars-Millennium-Falcon/3474788564",
    "https://www.walmart.com/ip/LEGO-City-Police-Station-60316/1388823900",
    "https://www.walmart.com/ip/LEGO-Creator-3-in-1-Exotic-Parrot-31136/4006938900",

    # ── Electronics ───────────────────────────────────────────────────────────
    "https://www.walmart.com/ip/Apple-AirPods-Pro-2nd-Gen-with-MagSafe-Charging-Case-USB-C/2401728848",
    "https://www.walmart.com/ip/Apple-AirPods-3rd-Generation-with-Lightning-Charging-Case/861386456",
    "https://www.walmart.com/ip/Sony-WH-1000XM5-Wireless-Industry-Leading-Noise-Canceling-Headphones/3614920965",
    "https://www.walmart.com/ip/Apple-iPad-9th-Generation-Wi-Fi-64GB-Space-Gray/483978365",
    "https://www.walmart.com/ip/onn-50-Class-4K-UHD-LED-Roku-Smart-TV-HDR-100012585/632027059",
    "https://www.walmart.com/ip/TCL-55-Class-4-Series-4K-UHD-HDR-Smart-Roku-TV/669879093",
    "https://www.walmart.com/ip/Samsung-55-Class-4K-Crystal-UHD-Smart-TV/989571551",
    "https://www.walmart.com/ip/Samsung-Galaxy-Tab-A8-10-5-64GB/958255933",
    "https://www.walmart.com/ip/DJI-Mini-3-Drone/1515453614",

    # ── Smart Home ────────────────────────────────────────────────────────────
    "https://www.walmart.com/ip/Amazon-Echo-Dot-5th-Gen-2022-release/1481586448",
    "https://www.walmart.com/ip/Google-Nest-Mini-2nd-Gen-Smart-Speaker/526555556",
    "https://www.walmart.com/ip/Ring-Video-Doorbell-Wired/289726938",

    # ── Kitchen ───────────────────────────────────────────────────────────────
    "https://www.walmart.com/ip/Ninja-AF101-Air-Fryer-4-Quart-Black/371862067",
    "https://www.walmart.com/ip/Instant-Pot-Duo-7-in-1-Electric-Pressure-Cooker-6-Quart/109028718",
    "https://www.walmart.com/ip/Keurig-K-Compact-Single-Serve-K-Cup-Pod-Coffee-Maker-Black/54830044",

    # ── Fitness ───────────────────────────────────────────────────────────────
    "https://www.walmart.com/ip/CAP-Barbell-20-lb-Dumbbell-Set-with-Rack/181766959",
    "https://www.walmart.com/ip/Yes4All-Vinyl-Dumbbell-Set-of-2-Available-in-Various-Sizes/1062898665",

    # ── Gardening & Outdoor ───────────────────────────────────────────────────
    "https://www.walmart.com/ip/Better-Homes-Gardens-6-Piece-Outdoor-Furniture-Set/974049092",
    "https://www.walmart.com/ip/Miracle-Gro-All-Purpose-Garden-Soil-2-cu-ft/46905453",
    "https://www.walmart.com/ip/Sun-Joe-Electric-Pressure-Washer/535953102",
    "https://www.walmart.com/ip/Craftsman-V20-20V-Cordless-Leaf-Blower/856107782",

    # ── Furniture ─────────────────────────────────────────────────────────────
    "https://www.walmart.com/ip/Mainstays-Belden-Park-Fabric-Multiple-Colors/993678890",
    "https://www.walmart.com/ip/Mainstays-Adjustable-Height-Standing-Desk/2241977856",
    "https://www.walmart.com/ip/Homefort-Big-Tall-400lb-Office-Chair/2194812695",
    "https://www.walmart.com/ip/Zinus-12-Inch-Green-Tea-Memory-Foam-Mattress/46894470",

    # ── Electric Bikes & Scooters ─────────────────────────────────────────────
    "https://www.walmart.com/ip/Gotrax-GXL-V2-Electric-Scooter/362804916",
    "https://www.walmart.com/ip/Hover-1-Alpha-Electric-Kick-Scooter/633537438",
    "https://www.walmart.com/ip/Jetson-Bolt-Pro-Folding-Electric-Bike/488759278",

]

# ── Target ────────────────────────────────────────────────────────────────────
TARGET_PRODUCTS = [

    # ── Pokemon TCG Target Exclusives — HIGHEST PRIORITY (<60 s sellout) ──────
    "https://www.target.com/p/pokemon-prismatic-evolutions-elite-trainer-box/-/A-93954435",
    "https://www.target.com/p/pokemon-trading-card-game-paldean-fates-elite-trainer-box/-/A-89432659",
    "https://www.target.com/p/pokemon-temporal-forces-booster-bundle/-/A-89952655",

    # ── LEGO Target Exclusives ────────────────────────────────────────────────
    "https://www.target.com/p/lego-icons-botanical-collection-wildflower-bouquet/-/A-86216138",
    "https://www.target.com/p/lego-star-wars-millennium-falcon-75375/-/A-89144452",
    "https://www.target.com/p/lego-icons-bouquet-of-roses-10328/-/A-87811695",
    "https://www.target.com/p/lego-technic-lamborghini-huracn-tecnica-42161/-/A-88516397",

    # ── Funko Pop Target Exclusives ───────────────────────────────────────────
    "https://www.target.com/p/funko-pop-obi-wan-kenobi-star-wars-exclusive/-/A-90522056",
    "https://www.target.com/p/funko-pop-daredevil-marvel-exclusive/-/A-90522051",

    # ── Gaming Consoles ───────────────────────────────────────────────────────
    "https://www.target.com/p/sony-playstation-5-pro-console/-/A-93620188",
    "https://www.target.com/p/nintendo-switch-2/-/A-94693225",
    "https://www.target.com/p/nintendo-switch-with-neon-blue-neon-red-joy-con/-/A-77464002",
    "https://www.target.com/p/xbox-series-s-512gb-console/-/A-80931811",
    "https://www.target.com/p/meta-quest-3-mixed-reality-headset-128gb/-/A-89254004",
    "https://www.target.com/p/meta-quest-2-advanced-all-in-one-virtual-reality-headset-128gb/-/A-80027191",

    # ── Gaming Controllers / Accessories ─────────────────────────────────────
    "https://www.target.com/p/sony-dualsense-wireless-controller-for-playstation-5/-/A-80790841",
    "https://www.target.com/p/nintendo-switch-pro-controller/-/A-54187797",
    "https://www.target.com/p/super-mario-bros-wonder-nintendo-switch/-/A-89222720",
    "https://www.target.com/p/xbox-wireless-controller/-/A-80931804",

    # ── Electronics ───────────────────────────────────────────────────────────
    "https://www.target.com/p/apple-airpods-pro-2nd-generation-with-magsafe-case-usb-c/-/A-85978622",
    "https://www.target.com/p/beats-flex-all-day-wireless-earphones/-/A-80886022",
    "https://www.target.com/p/amazon-echo-dot-5th-gen-2022-release/-/A-85731672",
    "https://www.target.com/p/ring-video-doorbell-wired/-/A-78555120",
    "https://www.target.com/p/wyze-cam-v3-1080p-hd-indoor-outdoor-ip65-wired-smart-home-security-camera/-/A-79622440",
    "https://www.target.com/p/jbl-charge-5-portable-bluetooth-speaker/-/A-84415661",
    "https://www.target.com/p/beats-studio-buds-true-wireless-noise-cancelling-earbuds/-/A-80885191",
    "https://www.target.com/p/samsung-55-class-4k-smart-tv/-/A-83832662",
    "https://www.target.com/p/dji-mini-3-drone/-/A-88237714",
    "https://www.target.com/p/gopro-hero12-black/-/A-89128004",
    "https://www.target.com/p/samsung-galaxy-tab-a8/-/A-86076503",

    # ── Kitchen ───────────────────────────────────────────────────────────────
    "https://www.target.com/p/instant-pot-duo-7-in-1-electric-pressure-cooker-6qt/-/A-53118427",
    "https://www.target.com/p/ninja-air-fryer-af101-4-quart/-/A-80037928",
    "https://www.target.com/p/keurig-k-mini-single-serve-k-cup-pod-coffee-maker/-/A-76743671",
    "https://www.target.com/p/nespresso-vertuo-pop-coffee-maker-and-espresso-machine/-/A-87625411",

    # ── Home ─────────────────────────────────────────────────────────────────
    "https://www.target.com/p/roomba-600-series-robot-vacuum-670/-/A-80044598",
    "https://www.target.com/p/shark-iq-robot-vacuum-rv1001ae/-/A-82684337",
    "https://www.target.com/p/levoit-core-300-air-purifier/-/A-82592539",

    # ── Beauty ────────────────────────────────────────────────────────────────
    "https://www.target.com/p/revlon-one-step-volumizer-original-1-0-hair-dryer-and-hot-air-brush/-/A-77911594",
    "https://www.target.com/p/philips-sonicare-4100-power-toothbrush-rechargeable-electric/-/A-78564124",
    "https://www.target.com/p/oral-b-io-series-4-rechargeable-electric-toothbrush/-/A-82616478",

    # ── Fitness ───────────────────────────────────────────────────────────────
    "https://www.target.com/p/fit-simplify-resistance-loop-exercise-bands-set-of-5/-/A-84388065",
    "https://www.target.com/p/liquid-i-v-hydration-multiplier-16-stick-packs/-/A-79939625",

    # ── Gardening ────────────────────────────────────────────────────────────
    "https://www.target.com/p/fiskars-bypass-pruning-shears/-/A-13467492",
    "https://www.target.com/p/miracle-gro-all-purpose-garden-soil-2cu-ft/-/A-13394878",
    "https://www.target.com/p/sun-joe-electric-pressure-washer/-/A-80706721",
    "https://www.target.com/p/hose-nozzle-spray-garden-heavy-duty/-/A-84558028",

    # ── Furniture ─────────────────────────────────────────────────────────────
    "https://www.target.com/p/threshold-upholstered-accent-chair/-/A-83610696",
    "https://www.target.com/p/mainstays-adjustable-height-standing-desk/-/A-86891564",
    "https://www.target.com/p/flash-furniture-mid-back-ergonomic-office-chair/-/A-78593612",
    "https://www.target.com/p/zinus-12-green-tea-memory-foam-mattress/-/A-52309614",

    # ── Electric Bikes & Scooters ─────────────────────────────────────────────
    "https://www.target.com/p/razor-e300-electric-scooter/-/A-51527468",
    "https://www.target.com/p/segway-ninebot-kickscooter-e2-plus/-/A-87221743",

    # ── Toys ─────────────────────────────────────────────────────────────────
    "https://www.target.com/p/hot-wheels-20-pack-basic-car-set/-/A-78450793",
    "https://www.target.com/p/barbie-dreamhouse/-/A-52293022",

]

# ── Footsites ─────────────────────────────────────────────────────────────────
FOOTSITES_PRODUCTS = [

    # ── Foot Locker — Air Jordan 1 ────────────────────────────────────────────
    "https://www.footlocker.com/product/jordan-retro-1-high-og-mens/DZ5485701.html",
    "https://www.footlocker.com/product/jordan-retro-1-high-og-mens/DZ5485130.html",
    "https://www.footlocker.com/product/jordan-retro-1-high-og-mens/DZ5485106.html",
    "https://www.footlocker.com/product/jordan-retro-1-high-og-mens/DZ5485402.html",
    "https://www.footlocker.com/product/jordan-retro-1-high-og-mens/DZ5485008.html",
    "https://www.footlocker.com/product/jordan-retro-1-low-og-mens/CZ0790102.html",
    "https://www.footlocker.com/product/jordan-retro-1-low-og-mens/CZ0790400.html",
    "https://www.footlocker.com/product/jordan-retro-1-low-og-mens/HQ6998600.html",

    # ── Foot Locker — Air Jordan 3 ────────────────────────────────────────────
    "https://www.footlocker.com/product/jordan-retro-3-mens/CT8532031.html",
    "https://www.footlocker.com/product/jordan-retro-3-mens/CT8532106.html",
    "https://www.footlocker.com/product/jordan-retro-3-mens/CT8532080.html",
    "https://www.footlocker.com/product/jordan-retro-3-mens/DN3707010.html",
    "https://www.footlocker.com/product/jordan-retro-3-mens/CT8532001.html",
    "https://www.footlocker.com/product/jordan-retro-3-mens/CT8532111.html",

    # ── Foot Locker — Air Jordan 4 (huge resale) ──────────────────────────────
    "https://www.footlocker.com/product/jordan-retro-4-mens/FQ8138006.html",
    "https://www.footlocker.com/product/jordan-retro-4-mens/AQ3816006.html",
    "https://www.footlocker.com/product/jordan-retro-4-mens/HF0747141.html",
    "https://www.footlocker.com/product/jordan-retro-4-mens/IB2772101.html",

    # ── Foot Locker — Air Jordan 5 ────────────────────────────────────────────
    "https://www.footlocker.com/product/jordan-retro-5-mens/DD0587140.html",
    "https://www.footlocker.com/product/jordan-retro-5-mens/HF0731100.html",
    "https://www.footlocker.com/product/jordan-retro-5-mens/FN7405001.html",

    # ── Foot Locker — Air Jordan 6 & 11 ──────────────────────────────────────
    "https://www.footlocker.com/product/jordan-retro-6-mens/T8529001.html",
    "https://www.footlocker.com/product/jordan-retro-6-mens/CT8529162.html",
    "https://www.footlocker.com/product/jordan-retro-6-mens/IH6010100.html",
    "https://www.footlocker.com/product/jordan-retro-11-mens/CT8012104.html",
    "https://www.footlocker.com/product/jordan-retro-11-mens/CT8012047.html",

    # ── Foot Locker — Air Jordan 13 ───────────────────────────────────────────
    "https://www.footlocker.com/product/jordan-retro-13-mens/HQ6541001.html",

    # ── Foot Locker — Nike Dunk High (huge demand) ────────────────────────────
    "https://www.footlocker.com/product/nike-dunk-high-retro-mens/DD1399100.html",
    "https://www.footlocker.com/product/nike-dunk-high-retro-mens/DD1399001.html",

    # ── Foot Locker — Air Max 1 (trending) ───────────────────────────────────
    "https://www.footlocker.com/product/nike-air-max-1-mens/HF4296100.html",
    "https://www.footlocker.com/product/nike-air-max-1-mens/FD9082100.html",

    # ── Foot Locker — Air Max 95 ──────────────────────────────────────────────
    "https://www.footlocker.com/product/nike-womens-air-max-95/HJ5996001.html",

    # ── Foot Locker — New Balance Collabs ────────────────────────────────────
    "https://www.footlocker.com/product/new-balance-550-mens/BB550WT1.html",
    "https://www.footlocker.com/product/new-balance-550-mens/BB550LGY.html",
    "https://www.footlocker.com/product/new-balance-990v6-mens/M990GY6.html",

    # ── Foot Locker — Adidas ──────────────────────────────────────────────────
    "https://www.footlocker.com/product/adidas-originals-samba-mens/B75806.html",
    "https://www.footlocker.com/product/adidas-originals-samba-mens/B75807.html",
    "https://www.footlocker.com/product/adidas-originals-samba-mens/JR0881.html",
    "https://www.footlocker.com/product/adidas-originals-samba-mens/KJ6073.html",
    "https://www.footlocker.com/product/adidas-originals-handball-spezial-mens/BD7632.html",
    "https://www.footlocker.com/product/adidas-originals-handball-spezial-mens/IG6192.html",
    "https://www.footlocker.com/product/adidas-originals-handball-spezial-mens/JH5437.html",
    "https://www.footlocker.com/product/adidas-originals-handball-spezial-mens/KJ6016.html",
    "https://www.footlocker.com/product/adidas-originals-campus-00s-mens/JP6903.html",
    "https://www.footlocker.com/product/adidas-originals-campus-00s-mens/JR7287.html",
    "https://www.footlocker.com/product/adidas-originals-gazelle-indoor-mens/JH5405.html",
    "https://www.footlocker.com/product/adidas-originals-forum-low-cl-mens/HQ7474.html",

    # ── Champs Sports — Air Jordan 1 ──────────────────────────────────────────
    "https://www.champssports.com/product/jordan-aj-1-retro-high-og-v3-mens/H4363100.html",
    "https://www.champssports.com/product/jordan-retro-1-high-og-mens/Z5485003.html",
    "https://www.champssports.com/product/jordan-retro-1-high-og-mens/Z5485008.html",
    "https://www.champssports.com/product/jordan-aj-1-retro-low-og-mens/Q6998600.html",

    # ── Champs Sports — Jordan 3/4/5/6/8/9 ───────────────────────────────────
    "https://www.champssports.com/product/jordan-retro-3-mens/N3707202.html",
    "https://www.champssports.com/product/jordan-air-jordan-4-retro-og-fc-mens/M4002100.html",
    "https://www.champssports.com/product/jordan-retro-4-lakers-mens/FV415029.html",
    "https://www.champssports.com/product/jordan-retro-4-mens/FQ8138006.html",
    "https://www.champssports.com/product/jordan-retro-5-og-mens/Q7978101.html",
    "https://www.champssports.com/product/jordan-retro-5-mens/DD0587140.html",
    "https://www.champssports.com/product/jordan-retro-4-mens/AQ3816006.html",
    "https://www.champssports.com/product/jordan-retro-6-mens/T8529001.html",
    "https://www.champssports.com/product/jordan-retro-8-mens/35381100.html",
    "https://www.champssports.com/product/jordan-retro-9-mens/V4794100.html",

    # ── Champs Sports — New Balance ───────────────────────────────────────────
    "https://www.champssports.com/product/new-balance-550-mens/BB550WT1.html",
    "https://www.champssports.com/product/new-balance-990v6-mens/M990GY6.html",

    # ── Champs Sports — Air Max 1 ─────────────────────────────────────────────
    "https://www.champssports.com/product/nike-air-max-1-mens/FD9082100.html",
    "https://www.champssports.com/product/nike-womens-air-max-95/HJ5996001.html",

    # ── Champs Sports — Spizike Low ───────────────────────────────────────────
    "https://www.champssports.com/product/jordan-spizike-low-mens/Q1759001.html",
    "https://www.champssports.com/product/jordan-spizike-low-mens/Q1759005.html",
    "https://www.champssports.com/product/jordan-spizike-low-v2-mens/H1782200.html",

    # ── Kids Foot Locker ──────────────────────────────────────────────────────
    "https://www.kidsfootlocker.com/product/jordan-air-jordan-3-retro-og-boys-grade-school/B8968004.html",
    "https://www.kidsfootlocker.com/product/jordan-air-jordan-retro-11-ss-boys-grade-school/B1378001.html",
    "https://www.kidsfootlocker.com/product/jordan-retro-11-boys-grade-school/IH622364.html",
    "https://www.kidsfootlocker.com/product/jordan-retro-1-high-boys-preschool/H4283100.html",

]

# ── Nike SNKRS — style codes monitored for restocks / new availability ────────
NIKE_STYLE_CODES = [

    # ── Air Jordan 1 High OG ─────────���───────────────────────────────────────
    "DZ5485-701",  # Yellow Ochre
    "DZ5485-130",  # Green Glow
    "FQ2947-100",  # Bleached Denim
    "HV6674-067",  # High '85 "Bred / Banned"
    "DZ5485-106",  # Black Toe Reimagined
    "HV8563-600",  # Union x High OG
    "DZ5485-402",  # UNC Reimagined
    "DZ5485-008",  # Shattered Backboard Reimagined

    # ── Air Jordan 1 Low OG ───────────────────────────────────────────────────
    "CZ0790-102",  # Mocha
    "CZ0790-400",  # Obsidian
    "IH2309-500",  # Voodoo Alternate
    "IB8958-001",  # Nigel Sylvester x Low OG
    "HQ6998-600",  # Low OG "Chicago"
    "DM7866-104",  # Travis Scott x Fragment Low

    # ── Air Jordan 3 ─────────────────────────────────────────────────────────
    "CT8532-031",  # Green Glow
    "CT8532-106",  # Cement Grey
    "CT8532-080",  # Fear
    "DN3707-010",  # Black Cement OG 2024
    "CT8532-001",  # Black Cat
    "IB1482-100",  # OG "Seoul 2.0"
    "IB8967-004",  # OG "Rare Air"
    "CT8532-111",  # Pure Money
    "IO1752-100",  # Mexico "El Vuelo"

    # ── Air Jordan 4 ─────────────────────────────────────────────────────────
    "FQ8138-006",  # Bred Reimagined 2024
    "AQ3816-006",  # Military Blue 2024
    "DH6927-111",  # White Thunder
    "CT8527-016",  # Black Canvas
    "HF0747-141",  # Fear Pack 2025
    "IB2772-101",  # Metallic Green 2025

    # ── Air Jordan 5 ─────────────────────────────────────────────────────────
    "DD0587-140",  # White Cement 2025
    "HF0731-100",  # Aqua 2025
    "FN7405-001",  # Olive 2024

    # ── Air Jordan 6 ─────────────────────────────────────────────────────────
    "CT8529-162",  # Reverse Oreo 2025
    "IH6010-100",  # Georgetown 2025

    # ── Air Jordan 9 ─────────────────────────────────────────────────────────
    "FQ7792-100",  # AJ9 "Powder Blue" 2025

    # ── Air Jordan 11 ─────────────────────────────────────────────────────────
    "CT8012-104",  # Legend Blue / Columbia 2024
    "HQ7000-001",  # Low "Year of the Snake"
    "FV5104-006",  # Low Bred
    "IH0296-400",  # Rare Air Deep Royal/Fire Red
    "CT8012-047",  # Gamma Blue 2025
    "IO8959-133",  # 285 / Atlanta (30th Anniv.)
    "IO8960-707",  # H-Town / Houston (30th Anniv.)
    "IO8961-553",  # Mojave / Las Vegas (30th Ann.)
    "FV5104-100",  # Low University Blue

    # ── Air Jordan 12 ─────────────────────────────────────────────────────────
    "CT8013-006",  # Black Taxi 2024
    "FV6126-106",  # Field Purple 2025

    # ── Air Jordan 13 ─────────────────────────────────────────────────────────
    "HQ6541-001",  # AJ13 "Wolf Grey" 2025
    "HQ6540-001",  # AJ13 "Obsidian" 2025

    # ── Air Jordan 14 ─────────────────────────────────────────────────────────
    "HM4789-100",  # AJ14 "Flint Grey" 2025

    # ── Air Jordan 2 ─────────────────────────────────────────────────────────
    "DX2454-101",  # AJ2 "White/Varsity Royal"

    # ── Nike Dunk Low ─────────────────────────────────────────────────────────
    "DD1391-100",  # Panda (restock)
    "FB7173-001",  # Black White 2024
    "FZ5765-001",  # Year of the Snake 2025
    "HF0461-001",  # Georgetown 2025

    # ── Nike Dunk High ────────────────────────────────────────────────────────
    "DD1399-100",  # Dunk High White
    "DD1399-001",  # Dunk High Black

    # ── Nike SB Dunk (skate-to-street crossover) ──────────────────────────────
    "HF7537-001",  # SB Dunk Low Pro
    "DV0833-101",  # SB Dunk High Pro

    # ── Air Force 1 ──────────────────────────────────────────────────────────
    "CW2288-111",  # White (restock)
    "FV0383-001",  # Year of the Snake 2025

    # ── Air Max 1 ────────────────────────────────────────────────────────────
    "HF4628-001",  # Travis Scott x Air Max 1 2025
    "FD9082-100",  # Air Max 1 Premium
    "HF4296-100",  # Air Max 1 "Alabaster"

    # ── Air Max 95 ────────────────────────────────────────────────────────────
    "HJ5996-001",  # Women's Air Max 95 Pink Foam

    # ── Air Max / Other Heat ──────────────────────────────────────────────────
    "HF9982-001",  # Air Max 97 Year of the Snake 2025
    "FB9109-200",  # Air Max Plus OG Desert Sand 2025
    "IM9113-300",  # User-flagged upcoming drop

    # ── Air Foamposite (huge collector item) ──────────────────────────────────
    "FV6126-600",  # Air Foamposite Pro "Phoenix Suns"
    "HM4490-001",  # Air Foamposite One "Anthracite" 2025

]

# SNKRS channel ID — filters to SNKRS-exclusive drops
SNKRS_CHANNEL_ID = "010794e5-35fe-4e32-aaff-cd2c74f89d61"