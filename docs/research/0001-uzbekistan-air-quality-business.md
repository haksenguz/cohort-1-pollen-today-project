---
status: active
owner: Ismoiljon
review-by: 2026-11-11
verified: partially — every number below carries a source; none re-measured by us
---

# 0001 — Air pollution in Uzbekistan as a business

## The question

From the notebook, 8 June: air pollution problems in Uzbekistan, what solutions
exist, how the government is reacting. Then the real question. Somebody abroad
is already making money on this. Can we copy the model, run it in Uzbekistan,
and raise money on it?

Short answer: yes, but not the part you would guess. Selling clean-air data to
citizens is the weak business. Selling compliance to companies that are now
legally required to measure is the strong one. The law that created that demand
is fourteen months old.

## What is actually true

| Fact | Value | Source |
| --- | --- | --- |
| Population | 38.2M, growing ~1M a year | [Statista/Wikipedia](https://en.wikipedia.org/wiki/Economy_of_Uzbekistan) |
| GDP per capita | $4,661 nominal, $14,179 PPP | same |
| Internet users on a phone | 89% of all users | [101digital](https://101digital.uz/en/blog/uzbekistan-digital-marketing-report-2026/) |
| Tashkent PM2.5, 2024 average | 31.5 µg/m³, about 6.3× the WHO guideline | [IQAir](https://www.iqair.com/air-quality/uzbekistan/toshkent-shahri/tashkent) |
| Tashkent on a bad winter day | 3rd most polluted major city on earth, AQI over 200 | [IQAir newsroom, 4 Dec 2025](https://www.iqair.com/newsroom/tashkent-among-the-most-polluted-cities-in-the-world-12-4-2025) |
| Deaths from PM2.5 | 89 per 100,000 in 2019, worst in Central Asia | [World Bank](https://www.worldbank.org/en/region/eca/publication/air-quality-management-in-central-asia) |
| Annual cost, Tashkent alone | $488.4M, roughly 0.7% of national GDP | [World Bank Tashkent assessment](https://www.worldbank.org/en/country/uzbekistan/publication/air-quality-assessment-for-tashkent) |
| Share of Tashkent residents in high-pollution zones | 83% | [kun.uz on the World Bank report](https://kun.uz/en/news/2024/10/09/world-bank-report-83-of-tashkent-residents-live-in-high-air-pollution-zones) |

Where it comes from matters for what you can sell. Heating is about 28% of
annual PM2.5, transport 12% in winter and up to 25% in late summer, industry
12-13% year round, and windblown desert dust roughly 36% of the summer load.
Dust and heating are seasonal. Construction and traffic are not.

## What the government did, and why the timing is the whole opportunity

This is the part that turns a social problem into a purchase order.

- March 2025: a law fining construction companies that exceed dust limits on
  sites over 500 m². Non-compliance now costs five times the old pollution fee.
  ([Envirotech](https://www.envirotech-online.com/news/ambient-air-quality/162/international-environmental-technology/uzbekistan-air-monitoring-reforms-new-instrument-market/65433))
- 25 November 2025: a presidential decree on urgent measures for Tashkent air.
  It bans A-80 fuel and pre-2010 vehicles below Euro-4, pushes polluting plants
  out of the city, and requires construction sites to run water sprayers, green
  buffers and their own monitoring stations.
  ([Gazeta.uz](https://www.gazeta.uz/en/2025/11/25/ecology/))
- The same decree creates the Air Monitoring Uzbekistan network and a Special
  Commission that had to be standing by 1 March 2026.
- 347 small automated background stations nationwide, plus 25 automated stations
  across Tashkent and its industrial belt by 2026, with public display boards.

A regulator that fines you is a better customer-creator than a regulator that
asks nicely. Every site over 500 m² in Tashkent now needs a number it can show
an inspector. Most of them do not have one.

## Who already makes money from this, worldwide

| Company | Model | Outcome |
| --- | --- | --- |
| BreezoMeter | Air quality API sold to healthcare, automotive, smart home and purifier brands | Raised $12.5M, [acquired by Google in 2022](https://app.dealroom.co/companies/breezometer) |
| [Airly](https://finance.yahoo.com/news/airly-fights-air-pollution-network-064513194.html) | Cheap sensors plus a dashboard, sold to city governments | $8.8M raised, 500+ local authorities in 40+ countries, 5,000 sensors |
| [Clarity](https://www.clarity.io/blog/the-roi-of-air-quality-monitoring-how-to-budget-and-justify-the-investment) | Sensor network sold as hardware plus a data subscription | Sensing-as-a-service, recurring revenue on top of device sales |
| IQAir | Purifiers, a consumer app, and outdoor monitors | Global purifier market was [$18.1B in 2025 heading to $30.1B by 2033](https://www.coherentmarketinsights.com/industry-reports/air-purifier-market) |

The pattern across all four is the same, and it is worth stating plainly.
Nobody built a large business by charging citizens for air data. BreezoMeter
made its money [selling the data into other companies' products](https://breezometer.medium.com/how-to-build-a-successful-monetization-strategy-with-environmental-data-d0c01276310c).
Airly sells to municipalities. Clarity sells hardware then bills a subscription
against it. The consumer app is the marketing, not the revenue.

## Who is already here

- **air.tashkent.uz**, the city's open data portal, hourly station data with
  seven days of history. ([launched March 2024](https://www.gazeta.uz/en/2024/03/20/air-quality/))
- **uhavo.uz** and **monitoring.meteo.uz**, government-side monitoring.
- **Uzum × IQAir**: Uzum bolted IQAir AirVisual Outdoor monitors onto its own
  pickup points, branches and logistics hubs across the country, feeding the
  IQAir app. ([IQAir newsroom](https://www.iqair.com/us/newsroom/revealing-the-invisible-uzum-uzbekistan))

Read that last one carefully, because it is a warning. Uzum did not build a
sensor business. It bought a foreign vendor's hardware and used air quality as
brand marketing on infrastructure it already owned. A newcomer cannot win that
game on distribution. It has to win on something Uzum does not want to do.

Note also what the government portals prove: the public consumer layer is free
and already exists. That is exactly the situation this pollen project is in with
KMA data, and the same lesson applies. The scarce thing is not the measurement.
It is delivery, accountability and a signed report.

## Where the money is, ranked

**1. Construction dust compliance as a service.** The decree tells sites to
monitor. Nobody tells them how. Sell a rented monitor on the fence line, a
dashboard, threshold alerts by SMS, and a monthly PDF an inspector accepts.
Britain has a whole industry doing exactly this against its PM10 threshold of
50 µg/m³, built on rental rather than sale
([example](https://www.euroenvironmental.co.uk/pages/construction-dust-monitoring)).
Recurring revenue, a legal buying trigger, and a customer who is comparing your
price against a fine rather than against zero. Start here.

**2. Indoor air for schools, clinics and offices.** Uzbekistan already carries
the region's highest childhood atopic dermatitis incidence, 1,185 per 100,000
in 2021 ([GBD 2021](https://bmcpulmmed.biomedcentral.com/articles/10.1186/s12890-025-03518-y)).
Private schools and clinics buy on parent anxiety, not on regulation, which
means shorter sales cycles and worse margins. Pair a monitor with filter
replacement on subscription so the revenue does not stop after the install.

**3. Purifier and filter distribution.** Fastest cash, no moat at all. Useful
only as a way to fund the sensor business and to learn who the buyers are.
Asia's purifier market alone runs [$3.13B in 2025 to $6.88B by 2032](https://www.marknteladvisors.com/research-library/asia-air-purifier-market-report.html).

**4. Industrial emissions reporting.** Plants being relocated out of Tashkent
need compliance documentation. Small number of customers, large contracts, slow
and political. Later.

**5. A consumer app and API.** Do it, but do not price it. It is the credibility
and the recruiting story that makes options 1 and 2 sellable, and it is the
asset an acquirer eventually wants. BreezoMeter's exit says the API is worth
something. It also says the API alone raised only $12.5M in eight years.

## Why the copy can work here

- **Taxes.** IT Park residents pay no corporate income tax, no VAT, no turnover
  tax through 2028, and 7.5% employee income tax instead of 12%. Export-heavy
  residents keep relief [to 2040](https://legalact.uz/en/news/it-park-uzbekistan-key-tax-benefits-and-extensions-until-2040),
  and imported technical equipment comes in duty-free until 2040. For a company
  importing sensors, that customs line is real money.
- **One catch.** From 1 April 2026 marketplaces, payment providers and
  microfinance lose IT Park incentives. A sensor plus SaaS company is not on
  that list, so this stays available. Do not bolt a payments product onto it.
- **Money exists.** IT Park Ventures went from $10M to
  [$30M in 2026](https://www.uzdaily.uz/en/it-park-ventures-expands-fund-to-us30-million/)
  and matches foreign investment up to $100,000. Twelve-plus local funds hold
  over $136M. The Green Start accelerator ran its demo day in June 2026, the
  government has committed up to $20M in green grants alongside EBRD, and EBRD
  put $30M of green lending through Hamkorbank.
- **Proof that scale is possible.** Uzum went from nothing to
  [$2.3B and $691M of 2025 revenue](https://techcrunch.com/2026/03/10/uzbekistans-uzum-valuation-rises-1-5x-in-seven-months-to-2-3b/)
  in about four years, with Tencent on the cap table and an IPO being discussed
  for 2027. Kaspi built the same playbook next door in Kazakhstan and is now
  [worth billions on Nasdaq](https://www.stocktitan.net/news/KSPI/kaspi-kz-1q-2026-financial-1mi5o3rpvr7a.html).
  Investors here have seen a local company reach that size. They will fund the
  next attempt.

## What could kill it

The government is buying 347 stations itself. If Air Monitoring Uzbekistan ends
up publishing free, dense, per-district data with an open API, the data layer is
worth nothing and only the compliance paperwork survives. I would treat that as
the likely case and plan the business so it still works when the data is free.

Second risk: calibration. Cheap optical sensors drift badly in heavy mineral
dust, and 36% of the summer load here is exactly that. A number an inspector
rejects is worth zero. Budget for a reference-grade unit and a documented
calibration procedure from day one.

Third: collection. Construction firms are slow payers everywhere, and here the
buyer may prefer the fine.

## What I would test first

Four cheap experiments, none needing a product.

1. Call twenty Tashkent construction firms with sites over 500 m². Ask what they
   currently do about the dust rule and what an inspection has cost them. That
   single call decides whether option 1 is real.
2. Get the actual text of the March 2025 dust law and the November 2025 decree,
   in Uzbek, and read what monitoring is specified. Everything above rests on
   press summaries of those two documents.
3. Price a landed IQAir AirVisual Outdoor and one reference-grade PM analyser
   against a rented Airly-class unit, with the IT Park customs exemption applied.
4. Ask air.tashkent.uz whether an API exists and under what licence.

## Still a hypothesis

Nothing here is measured by us. The prevalence figure for respiratory illness in
Uzbekistan is the weakest link, because I could not find a national asthma or
allergic rhinitis study and fell back on regional comparisons. No Uzbek customer
has been interviewed. The willingness of a construction firm to pay monthly for
compliance is an assumption, and it is the assumption the whole ranking rests
on.

## Relationship to this project

Same shape, different pollutant. Pollen Today takes free public government data
and wins on delivery timing rather than on measurement. An air quality business
in Tashkent takes free public government data and wins on accountability rather
than on measurement. The alert job, the region enum and the scheduler built here
are the reusable parts. The model is not.

## Sources

- [IQAir, Tashkent air quality](https://www.iqair.com/air-quality/uzbekistan/toshkent-shahri/tashkent)
- [IQAir newsroom, Tashkent among most polluted, 4 Dec 2025](https://www.iqair.com/newsroom/tashkent-among-the-most-polluted-cities-in-the-world-12-4-2025)
- [World Bank, air quality management in Central Asia](https://www.worldbank.org/en/region/eca/publication/air-quality-management-in-central-asia)
- [World Bank, air quality assessment for Tashkent](https://www.worldbank.org/en/country/uzbekistan/publication/air-quality-assessment-for-tashkent)
- [kun.uz, 83% of Tashkent residents in high-pollution zones](https://kun.uz/en/news/2024/10/09/world-bank-report-83-of-tashkent-residents-live-in-high-air-pollution-zones)
- [Gazeta.uz, presidential decree on Tashkent air, 25 Nov 2025](https://www.gazeta.uz/en/2025/11/25/ecology/)
- [Envirotech Online, Uzbekistan air monitoring reform and the instrument market](https://www.envirotech-online.com/news/ambient-air-quality/162/international-environmental-technology/uzbekistan-air-monitoring-reforms-new-instrument-market/65433)
- [Gazeta.uz, Air Tashkent portal launch](https://www.gazeta.uz/en/2024/03/20/air-quality/)
- [IQAir, Uzum monitoring network](https://www.iqair.com/us/newsroom/revealing-the-invisible-uzum-uzbekistan)
- [Dealroom, BreezoMeter](https://app.dealroom.co/companies/breezometer)
- [BreezoMeter on environmental data monetization](https://breezometer.medium.com/how-to-build-a-successful-monetization-strategy-with-environmental-data-d0c01276310c)
- [Airly sensor network](https://finance.yahoo.com/news/airly-fights-air-pollution-network-064513194.html)
- [Clarity, ROI of air quality monitoring](https://www.clarity.io/blog/the-roi-of-air-quality-monitoring-how-to-budget-and-justify-the-investment)
- [Euro Environmental, UK construction dust monitoring](https://www.euroenvironmental.co.uk/pages/construction-dust-monitoring)
- [Coherent Market Insights, air purifier market](https://www.coherentmarketinsights.com/industry-reports/air-purifier-market)
- [MarkNtel, Asia air purifier market](https://www.marknteladvisors.com/research-library/asia-air-purifier-market-report.html)
- [LegalAct.uz, IT Park tax benefits to 2040](https://legalact.uz/en/news/it-park-uzbekistan-key-tax-benefits-and-extensions-until-2040)
- [PwC, Uzbekistan tax credits and incentives](https://taxsummaries.pwc.com/republic-of-uzbekistan/corporate/tax-credits-and-incentives)
- [UzDaily, IT Park Ventures expands to $30M](https://www.uzdaily.uz/en/it-park-ventures-expands-fund-to-us30-million/)
- [Startup Genome, Uzbekistan ecosystem](https://startupgenome.com/report/gser2025/uzbekistan-central-asias-fastest-rising-startup-ecosystem)
- [UzDaily, Green Start accelerator demo day](https://www.uzdaily.uz/en/uzbekistan-green-start-accelerator-highlights-sustainable-startups/)
- [EBRD green lending via Hamkorbank](https://news.fundsforngos.org/2026/01/01/ebrd-supports-green-lending-in-uzbekistan-to-boost-sustainable-finance/)
- [TechCrunch, Uzum at $2.3B](https://techcrunch.com/2026/03/10/uzbekistans-uzum-valuation-rises-1-5x-in-seven-months-to-2-3b/)
- [Kaspi.kz Q1 2026 results](https://www.stocktitan.net/news/KSPI/kaspi-kz-1q-2026-financial-1mi5o3rpvr7a.html)
- [101digital, Uzbekistan digital marketing report 2026](https://101digital.uz/en/blog/uzbekistan-digital-marketing-report-2026/)
- [GBD 2021 allergic disease in children](https://bmcpulmmed.biomedcentral.com/articles/10.1186/s12890-025-03518-y)
