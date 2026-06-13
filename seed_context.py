"""Run once to seed the African/Nigerian finance context index."""

from vector_store import seed_africa_context

AFRICA_CONTEXT = [
    "Nigerians use P2P crypto to bypass CBN restrictions on forex access",
    "The CBN banned banks from servicing crypto exchanges in 2021, then reversed in 2023",
    "Binance Nigeria controversy: Tigran Gambaryan detained, billions in alleged capital flight",
    "Nigeria has one of the highest crypto adoption rates in the world by population",
    "Naira devaluation makes dollar-denominated crypto a savings tool for Nigerians",
    "USDT is the most traded crypto asset in Nigeria due to dollar scarcity",
    "Ghana, Kenya, and South Africa are the other major African crypto markets",
    "Africa's remittance market is worth over $100 billion annually — crypto is disrupting it",
    "Mobile money (M-Pesa) in East Africa competes with and complements crypto",
    "South African rand volatility drives local crypto demand similar to Nigeria",
    "The eNaira (Nigeria's CBDC) has had very low adoption since launch in 2021",
    "African stablecoin projects aim to create local-currency pegged assets",
    "Power outages and internet costs are real barriers to crypto adoption in rural Africa",
    "Nigerian fintech startups like Flutterwave and Paystack bridge crypto and traditional finance",
    "Crypto is used in Nigeria to pay for international subscriptions, tuition, and imports",
    "DeFi protocols with low gas fees (Solana, Tron, BSC) are more popular in Africa than Ethereum mainnet",
    "Bitcoin halving events historically trigger bull runs that African retail investors participate in",
    "FX restrictions in Nigeria mean crypto is one of the few ways to hold USD savings",
    "Naira devaluation forces retail savers to look for dollar-pegged assets like USDT",
    "High inflation in Nigeria reduces the real purchasing power of middle-class salaries",
    "CBN interest rate hikes aim to defend the Naira but increase the cost of local business loans",
    "Fuel subsidy adjustments and floating the currency heavily impact consumer tech adoption",
    "African Eurobonds dictate national debt sustainability and foreign exchange liquidity",
    "Traditional Nigerian banks are launching digital arms to compete directly with fintech startups",
]

if __name__ == "__main__":
    seed_africa_context(AFRICA_CONTEXT)
    print("Done. Africa context seeded successfully.")
