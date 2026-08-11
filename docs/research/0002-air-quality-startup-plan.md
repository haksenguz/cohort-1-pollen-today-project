---
status: active
owner: Ismoiljon
review-by: 2026-11-11
verified: partially — competitor pricing is public-source; our own prices are proposals, not tested
---

# 0002 — Startup plan: how the money is made, and how we would make it

Builds on [0001](0001-uzbekistan-air-quality-business.md). That file asked
whether air quality is a business in Uzbekistan. This one studies the companies
that already run it, then lays out the product, the price list, the way we sell
it over the internet, and the path to state money.

Working name: **Havo**. Cheap to say, spells what it does, works in Uzbek and
Russian.

## Part 1. Who makes money, and exactly how

I looked at ten companies. Nine of them sell the same three things in different
proportions: a box, a subscription, and a report.

| Company | What they charge for | Public price | The lesson |
| --- | --- | --- | --- |
| [Airly](https://airly.org/en/) (PL) | Sensor plus platform, sold to cities | Device €100–300, subscription from €15/month | 500+ local governments in 40+ countries on $8.8M raised. Cheap hardware, wide net |
| [Clarity](https://www.clarity.io/blog/cost-of-air-quality-monitoring-a-pricing-guide-for-cities-agencies) (US) | Sensing-as-a-Service, one flat annual fee | $500–5,000 per unit-year, all in | Bundles connectivity, calibration and replacement so the buyer never sees a surprise invoice |
| [Kaiterra](https://learn.kaiterra.com/en/resources/how-much-does-iaq-monitoring-cost) (CN/US) | Indoor monitors for commercial buildings | 10 monitors over 3 years for $12,100 | Killed its famous consumer product to go B2B only. That decision is the whole story |
| IQAir (CH) | Purifiers, monitors, a free app | Consumer retail | The free app is a lead magnet for hardware. It also got them the Uzum deal |
| [Respirer](https://respirer.in/) (IN) | Low-cost validated monitors for government and industry | Not public | Won a [$572k two-year contract](https://www.openphilanthropy.org/grants/respirer-living-sciences-national-clean-air-programme-tracker/) to run a national policy tracker. Data credibility became the product |
| [Oizom](https://oizom.com/air-quality-monitoring-system-manufacturers-in-india/) (IN) | Outdoor monitors and analytics | Not public | 3,000+ devices across 200+ municipalities. Municipal sales compound |
| [AirGradient](https://www.airgradient.com/) (TH) | Open-source monitors, kits and assembled | €150–300 outdoor, DIY kit about half | Open hardware plus published prices as a marketing weapon against opaque rivals |
| PurpleAir (US) | Consumer sensors, paid API | Points-based API billing, own-sensor data free | Gave away the map, charged for programmatic access |
| [uHoo](https://allergystore.com/products/uhoo-indoor-air-quality-sensor) (HK) | Indoor monitor plus premium app | Device, then $9.99/month | Classic razor and blades on a $300 device |
| [BreezoMeter](https://app.dealroom.co/companies/breezometer) (IL) | Air quality API into other firms' products | Enterprise API | $12.5M raised, bought by Google in 2022. No hardware at all |

For contrast, the incumbent option that governments buy today: a reference-grade
regulatory monitor costs $15,000 to $40,000 and over $15,000 a year to maintain
(Clarity's guide, linked above). That gap between $40,000 and $900 is the entire
market opening. Nobody can afford dense coverage with reference monitors. Every
company in the table above exists because of that arithmetic.

### The four rules I take from this

1. **The box is the wedge, the subscription is the business.** Airly, Clarity,
   Kaiterra and uHoo all sell hardware near cost and bill monthly forever.
2. **Consumers do not pay. Institutions do.** Kaiterra discontinued its consumer
   line on purpose. IQAir keeps its app free because the app sells purifiers.
3. **Credibility is a product.** Respirer's contract is for a policy tracker,
   not for sensors. Data somebody official will cite is worth more than data.
4. **Do not build the sensor.** The PM sensing element, a Plantower PMS5003, is
   [$17 to $40](https://shop.pimoroni.com/en-us/products/pms5003-particulate-matter-sensor-with-cable).
   AirGradient publishes its whole design. The moat is calibration, the network,
   and the report, never the plastic.

## Part 2. The product

Three layers. Build them in this order, and refuse to build layer three early.

**Layer 0, the node.** Outdoor unit: PM2.5 and PM10, temperature, humidity,
optionally NO2. LTE or NB-IoT, mains power with a battery bridge, magnetic or
strap mount for a site fence. Buy the sensing element, design only the housing
and the board. Target landed cost under $150, which the IT Park customs
exemption to 2040 makes realistic. One reference-grade unit sits at our own
office as the calibration anchor. That unit is not overhead. It is the thing
that makes our numbers arguable in front of an inspector.

**Layer 1, the platform.** This is where our existing skill transfers directly
from Pollen Today.

- ingest endpoint, one row per reading, time-series storage
- a calibration job that corrects raw sensor output against the reference unit
- threshold rules per site, with alerts pushed to Telegram inside 60 seconds
- a dashboard showing the last 7 and 30 days per site
- **the monthly PDF**, stamped, per site, listing exceedances, durations and
  actions taken

That PDF is the actual product. Everything above it is plumbing that makes the
PDF true. A site manager does not want air data. He wants a document he can hand
to an inspector without losing money.

**Layer 2, the public layer.** A free Telegram bot and a map for Tashkent.
Revenue: zero, deliberately. It exists to make us the name journalists call and
the name the Ecology Committee already knows before we bid on anything.

### MVP scope, six weeks

Reuse the stack this project already runs: FastAPI, Postgres, a schema-first
contract, a scheduler, a Telegram delivery job. Add device ingest and PDF
generation. That is the whole build.

What we do **not** build in the first six weeks: mobile apps, a forecast model,
NO2 or ozone, multi-tenant billing, or anything with the word platform in it.
Ten nodes, one city, five paying sites, one PDF template.

## Part 3. Prices we would charge

Anchored to the table above, adjusted down for local purchasing power. These are
proposals to test, not findings.

| Offer | Who buys | Price | Contract |
| --- | --- | --- | --- |
| Site compliance | Construction firm, site over 500 m² | $200–300 per site per month, node included | 12 months |
| Industrial | Factory being relocated or inspected | $500–700 per monitoring point per month | 12 months |
| Indoor for schools and clinics | Private schools, kindergartens, clinics | $30–50 per room per month, filters billed separately | 9 months, school year |
| Municipal network | Hokimiyat, Ecology Committee | $700–900 per node-year, all in | 3 years |
| Data API | Developers, insurers, real estate | Free tier, then tiered | monthly |

Sanity check on the unit: a $150 node against $250 a month means the hardware
pays for itself in under three weeks of service, and the rest is gross margin
against SIM, hosting and one site visit a quarter. One hundred sites is roughly
$300k a year recurring. That is the whole company at year two, and it needs
about six people.

## Part 4. Selling it over the internet

Uzbekistan is unusually good for internet-first selling, because one channel has
near-total reach. Telegram has [27 million users here, about 76% of the
population](https://101digital.uz/en/blog/telegram-marketing-uzbekistan/), with
Instagram at [17.4 million](https://stats.napoleoncat.com/instagram-users-in-uzbekistan/).
89% of internet users are on a phone. A recommended local budget split runs
Telegram 35%, Instagram 25%, Google 20%.

The sequence I would run, in order:

**Step 1, publish before selling.** Put ten nodes up around Tashkent and run a
free Telegram channel that posts the morning number, the evening number, and a
plain sentence about whether it is a bad day for children. Do it every single
day through a winter. Cost is hosting plus hardware. This is exactly what
Pollen Today does with KMA data, so we already know how to build it.

**Step 2, turn the channel into authority.** Once a month, publish a Tashkent
air report as a proper PDF with charts and district rankings. Send it to kun.uz,
Gazeta.uz and Spot.uz. Local press covers air pollution constantly and is short
of local data. Respirer's whole position in India came from being the group that
publishes the tracker everyone quotes.

**Step 3, one landing page, two buttons.** "Get a compliance quote for your
site" and "Buy a monitor". The first is a lead form, the second is a Uzum Market
listing so we never touch logistics. Consumer device sales fund the B2B sales
cycle and teach us who is buying.

**Step 4, outbound where the buyers are.** Construction firms are on Telegram,
not on LinkedIn. Get the site register, find the developer, message the site
manager with a screenshot of his own street's PM2.5 from our public map. That
message is the pitch. No deck.

**Step 5, tenders.** Register as a supplier on
[xarid.uz](https://www.selltostate.com/blog/xarid-uzbekistan-guide/) and watch
for anything from hokimiyats and the Ecology Committee. The state is buying 347
background stations and 25 Tashkent stations. Being on the supplier registry
before those tenders close is a cheap lottery ticket with a real prize.

**Step 6, paid pilots, never free ones.** The B2B literature is blunt about
this: free pilots get shelved and teach you nothing. Take $500 for a two-month
pilot. Before hardware exists, collect signed letters of intent that name the
price and the quantity, because an LOI carries more weight with our investors
than any market projection in this document.

## Part 5. Getting state money, which is the point

Uzbekistan is currently paying people to do this. The list, with what each one
requires:

| Source | Size | What it wants |
| --- | --- | --- |
| [President Tech Award](https://timesca.com/uzbekistan-expands-president-tech-award-to-5-million-launches-1-million-ai-startup-competition/) | $5M pool: $1M grants, $4M investment | Uzbek citizens, under 30, team of 3–8. Incubation track pays 25 winners out of $1M |
| [IT Park Ventures](https://www.uzdaily.uz/en/it-park-ventures-expands-fund-to-us30-million/) | $30M fund | Seed and Series A, matches foreign investment up to $100k |
| Startup Garage | Incubation in all 14 regions | 150+ startups incubated, now able to take direct IT Park Ventures money |
| [Green Start accelerator](https://www.uzdaily.uz/en/uzbekistan-green-start-accelerator-highlights-sustainable-startups/) | Demo day ran June 2026 | Sustainability framing, which we have for free |
| Government green grants with EBRD | up to $20M committed | Green sector entrepreneurship |
| [EBRD via Hamkorbank](https://news.fundsforngos.org/2026/01/01/ebrd-supports-green-lending-in-uzbekistan-to-boost-sustainable-finance/) | $30M green lending line | MSME lending, useful for hardware working capital |

Two things about this list matter more than the amounts.

First, **the team requirement is a build instruction**. The President Tech Award
takes teams of 3 to 8 under 30. Solo founders are not eligible. Assemble four
people before the application window, not after.

Second, **the state is both the customer and the investor here**, and that is
rare. A company that already runs a public air map the Ecology Committee cites
is not asking for a grant. It is asking for continuation of something the
government already decided to fund in a presidential decree. Grant committees
approve continuation and hesitate on invention. Sequence the public map before
the funding application, not after.

Tax position while doing all this: IT Park residency means no corporate income
tax, no VAT and no turnover tax through 2028, 7.5% payroll tax rather than 12%,
and duty-free import of technical equipment to 2040. On a hardware business the
customs line alone is worth several points of margin. The 1 April 2026 exclusion
covers marketplaces, payment providers and microfinance, so a sensor and
software company keeps the benefits. Do not add a payments feature.

## Part 6. Twelve months

| Quarter | Do | Spend | Proof it worked |
| --- | --- | --- | --- |
| Q1 | 20 customer calls, LOIs, 10 nodes assembled, public Telegram channel live | ~$5k | 5 signed LOIs naming a price |
| Q2 | Platform MVP, first monthly Tashkent report, 5 paid pilots at $500 | ~$15k | $2.5k collected, one press pickup |
| Q3 | Convert pilots to 12-month contracts, apply to President Tech Award and Green Start, register on xarid.uz | grant funded | 20 paying sites, about $5k monthly recurring |
| Q4 | 100 sites, hire two, first municipal or industrial contract | grant plus revenue | ~$25k monthly recurring, one state contract |

Kill criteria, written down now so we cannot argue with them later. If fewer
than 3 of the first 20 firms have paid an air-related fine or inspection cost,
the compliance thesis is wrong and we go indoor-first instead. If pilot to
contract conversion is under 40%, the PDF is not the product we think it is.

## Part 7. What breaks it

- The state opens a free dense API from its 347 stations and the data layer goes
  to zero. Plan for this. It is why the revenue sits in reports and compliance
  rather than in numbers.
- Desert dust wrecks cheap optical sensors. 36% of the summer load here is
  mineral dust. Without a reference unit and a documented calibration procedure,
  our readings get rejected and the business dies on the first dispute.
- Construction firms pay late, or prefer the fine. Charge quarterly in advance.
- A foreign vendor arrives with a state partner. Uzum already ships IQAir
  hardware. Our defence is the report, the local language, and the price.

## Sources

- [Clarity, cost of air quality monitoring for cities and agencies](https://www.clarity.io/blog/cost-of-air-quality-monitoring-a-pricing-guide-for-cities-agencies)
- [Kaiterra, how much IAQ monitoring costs](https://learn.kaiterra.com/en/resources/how-much-does-iaq-monitoring-cost)
- [AirGradient on IAQ industry pricing opacity](https://www.airgradient.com/blog/costs-aq-monitoring-wells/)
- [Airly](https://airly.org/en/) and [Airly PM+GAS listing](https://monitors.cleanairstars.com/upcp_product/airly-pm/)
- [Respirer Living Sciences](https://respirer.in/), [Open Philanthropy NCAP Tracker grant](https://www.openphilanthropy.org/grants/respirer-living-sciences-national-clean-air-programme-tracker/)
- [Oizom](https://oizom.com/air-quality-monitoring-system-manufacturers-in-india/)
- [Dealroom, BreezoMeter](https://app.dealroom.co/companies/breezometer)
- [Plantower PMS5003 pricing](https://shop.pimoroni.com/en-us/products/pms5003-particulate-matter-sensor-with-cable)
- [101digital, Telegram marketing in Uzbekistan](https://101digital.uz/en/blog/telegram-marketing-uzbekistan/)
- [NapoleonCat, Instagram users in Uzbekistan](https://stats.napoleoncat.com/instagram-users-in-uzbekistan/)
- [Guide to xarid.uz procurement portal](https://www.selltostate.com/blog/xarid-uzbekistan-guide/)
- [Times of Central Asia, President Tech Award expanded to $5M](https://timesca.com/uzbekistan-expands-president-tech-award-to-5-million-launches-1-million-ai-startup-competition/)
- [IT Park, Uzbekistan boosts startup funding](https://www.it-park.uz/en/itpark/news/uzbekistan-boosts-startup-funding-and-expands-youth-support)
- [UzDaily, IT Park Ventures at $30M](https://www.uzdaily.uz/en/it-park-ventures-expands-fund-to-us30-million/)
- [UzDaily, Green Start accelerator](https://www.uzdaily.uz/en/uzbekistan-green-start-accelerator-highlights-sustainable-startups/)
- [EBRD green lending via Hamkorbank](https://news.fundsforngos.org/2026/01/01/ebrd-supports-green-lending-in-uzbekistan-to-boost-sustainable-finance/)
- [Lean B2B, how founders sell their first product](https://leanb2bbook.com/blog/the-3-approaches-to-selling-your-first-product/)
- [Tinova, LOIs, design partners and pilots](https://tinovagency.com/blogs/letter-of-intent-startup-customers-lois-design-partners-pilots/)
