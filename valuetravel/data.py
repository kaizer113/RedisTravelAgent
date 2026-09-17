"""Fictional, deterministic inventory: no live prices or booking claims."""

MEMBERS = [
    {
        "member_id": "travel-alex",
        "name": "Alex Rivera",
        "tier": "Executive",
        "home_airport": "SFO",
        "household": "Two adults and two children",
        "preferences": [
            "Prefers nonstop flights from SFO.",
            "Travels with two children and values breakfast and a pool.",
        ],
    },
    {
        "member_id": "travel-maya",
        "name": "Maya Chen",
        "tier": "Executive",
        "home_airport": "SEA",
        "household": "Two adults",
        "preferences": [
            "Prefers quiet adults-only resorts and vegetarian dining.",
            "Likes flexible cancellation terms.",
        ],
    },
    {
        "member_id": "travel-jordan",
        "name": "Jordan Brooks",
        "tier": "Gold Star",
        "home_airport": "LAX",
        "household": "Two adults",
        "preferences": [
            "Prefers cultural trips and walkable neighborhoods.",
            "Likes keeping the total trip cost under 5000 dollars.",
        ],
    },
]
# name, destination, style, nights, party, price, card, airport, nonstop, breakfast
ROWS = [
    ("Kaanapali Family Escape", "Maui", "family", 5, 4, 5890, 250, "SFO", True, True),
    ("Wailea Ocean Retreat", "Maui", "family", 5, 4, 6490, 400, "SFO", True, True),
    ("Kihei Beachside Value", "Maui", "family", 5, 4, 4790, 100, "SFO", False, False),
    ("Waikiki Discovery", "Oahu", "family", 5, 4, 4390, 150, "SFO", True, True),
    ("Ko Olina Lagoon Stay", "Oahu", "family", 5, 4, 6290, 300, "SFO", True, True),
    ("Kona Coast Adventure", "Hawaii", "family", 6, 4, 5790, 200, "SFO", True, False),
    (
        "Riviera Maya All-Inclusive",
        "Cancun",
        "family",
        6,
        4,
        5290,
        250,
        "SFO",
        True,
        True,
    ),
    ("Los Cabos Family Sun", "Los Cabos", "family", 5, 4, 4890, 150, "SFO", True, True),
    (
        "Pacific Couples Hideaway",
        "Los Cabos",
        "adults-only",
        5,
        2,
        3790,
        200,
        "SEA",
        True,
        True,
    ),
    ("Riviera Serenity", "Cancun", "adults-only", 6, 2, 4290, 300, "SEA", True, True),
    (
        "Wailea Couples Escape",
        "Maui",
        "adults-only",
        5,
        2,
        4590,
        250,
        "SFO",
        True,
        True,
    ),
    ("Kapalua Quiet Coast", "Maui", "adults-only", 5, 2, 3990, 150, "SFO", True, False),
    (
        "Aruba Beach Retreat",
        "Aruba",
        "adults-only",
        6,
        2,
        4690,
        250,
        "SEA",
        False,
        True,
    ),
    ("Lisbon Neighborhoods", "Lisbon", "culture", 6, 2, 3690, 100, "LAX", False, True),
    ("Rome and Florence", "Italy", "culture", 8, 2, 4890, 200, "LAX", True, True),
    (
        "Barcelona City and Sea",
        "Barcelona",
        "culture",
        6,
        2,
        4090,
        150,
        "LAX",
        True,
        True,
    ),
    ("Paris Walkable Weekend", "Paris", "culture", 4, 2, 3890, 100, "LAX", True, False),
    (
        "San Juan Old Town",
        "Puerto Rico",
        "culture",
        5,
        2,
        3290,
        100,
        "LAX",
        False,
        True,
    ),
]
PACKAGES = []
for i, (
    name,
    dest,
    style,
    nights,
    party,
    price,
    card,
    airport,
    nonstop,
    breakfast,
) in enumerate(ROWS, 1):
    pid = f"VT-{i:03}"
    inclusions = ["Round-trip flights", "Hotel stay", "Airport transfers"]
    if breakfast:
        inclusions.append("Daily breakfast")
    if dest in ("Cancun", "Los Cabos"):
        inclusions.append("All-inclusive meals")
    if style == "family":
        inclusions.append("Pool access")
    PACKAGES.append(
        dict(
            package_id=pid,
            name=name,
            destination=dest,
            style=style,
            nights=nights,
            travelers=party,
            total_price=price,
            shop_card=card,
            home_airport=airport,
            nonstop=nonstop,
            breakfast=breakfast,
            inclusions=inclusions,
            description=f"{name}: {nights} nights in {dest} for {party} travelers. {style} vacation with "
            + ", ".join(inclusions)
            + (". Nonstop flights." if nonstop else ". One connection each way."),
            departure_date="2027-04-10",
            return_date=f"2027-04-{10 + nights:02}",
            currency="USD",
            available_rooms=3 + i % 7,
            eligible_reward_base=round(price * 0.8, 2),
            cancellation="Refundable hotel until 30 days before departure; flight fare rules apply."
            if i % 3
            else "Hotel becomes nonrefundable 14 days before departure; flight fare rules apply.",
            data_label="Synthetic demo offer",
        )
    )
POLICIES = [
    {
        "id": "package-inclusions",
        "title": "What is included in a vacation package?",
        "text": "VALUE TRAVEL demo packages include round-trip flights, hotel and airport transfers. Breakfast and all-inclusive meals vary by offer; compare the listed inclusions. All displayed package totals include the modeled taxes and mandatory fees. Optional excursions, baggage and travel protection are extra. All offers are fictional.",
    },
    {
        "id": "member-benefits",
        "title": "How do Executive member benefits work?",
        "text": "In this fictional VALUE TRAVEL demo, Executive members earn a modeled 2% reward on the eligible portion after travel is completed. The eligible base excludes modeled taxes and fees. The reward is not deducted from the amount payable. Gold Star members do not receive this modeled reward. A digital shop card, when included, is a separate future benefit, not a cash discount.",
    },
    {
        "id": "cancellation",
        "title": "How does cancellation work?",
        "text": "Cancellation terms depend on the offer and supplier. Check the current offer terms before making a decision. Refundable hotel periods do not imply refundable flights. VALUE TRAVEL only creates a simulated shortlist; it cannot book, cancel or charge a card.",
    },
    {
        "id": "rental-car",
        "title": "What should I check when renting a car?",
        "text": "Compare the total rental cost, pickup location, driver eligibility, additional-driver terms, insurance, fuel policy and cancellation rules. Inclusion in a vacation package must be confirmed from that offer. Never assume an additional driver or insurance is included.",
    },
]
RESERVATIONS = [
    {
        "reservation_id": "VTR-1001",
        "member_id": "travel-alex",
        "package_id": "VT-004",
        "status": "Demo reservation — no real booking",
        "departure_date": "2027-04-10",
        "balance_due": 2195,
        "notes": "Family of four; airport transfers included.",
    }
]
