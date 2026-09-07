# Release notes

Wat elke versie voor jou als gebruiker betekent.

---

## 2026.9.0 — in voorbereiding

Deze versie herindeelt de integratie zodat ze de werkelijke Renson-opbouw volgt. Je kunt functioneel
hetzelfde, maar je ziet het anders terug en **een aantal entiteit-id's verandert**. Lees dit voordat
je bijwerkt.

### Wat er beter wordt

- **Je installatie is nu herkenbaar.** In plaats van één apparaat "Renson Arean" zie je de Brain
  module, de HVAC module, je thermostaat, de drie apps die op de Brain draaien, en de warmtepomp zelf
  — met per app het versienummer dat ook in OpenMotics staat.
- **De drie "onbekende uitgangen" zijn opgelost.** Het bleken `Zone 1-afsluiter` (R1),
  `Bypass-klep` (OUT3) en één kanaal waar `hvac_config` niets aan toewijst (OUT1). De namen komen
  niet meer uit de code maar uit de installatie zelf: de app levert de bedradingskaart die je
  installateur bij de inbedrijfstelling heeft ingevuld.
- **Nieuwe metingen.** Zonetemperatuur, systeemdruk, aanvoer- en retourtemperatuur van de warmtepomp,
  buitentemperatuur en netspanning. Lees wel de kanttekening verderop — deze waarden komen langs een
  omweg binnen.
- **Wijzigingen zijn direct zichtbaar.** Verander je de temperatuur, dan reageert de kaart meteen in
  plaats van pas bij de volgende pollronde. En hij springt niet meer terug naar de oude waarde: een
  pollronde die net vóór de cyclus van de app valt kan je wijziging niet meer ongedaan maken.
- **Rustiger logboek.** Bij het opstarten meldt de integratie van elke gegevensbron of die werkt,
  daarna alleen nog wanneer er iets verandert. Een storing wordt één keer gemeld, niet elke
  pollronde opnieuw.
- **Elk pollinterval past nu bij zijn bron.** De thermostaat elke 10 seconden, de kleppen en pompen
  elke 30, de app-instellingen elke 5 minuten, de moduleslijst elk kwartier.

### Wat je moet aanpassen

**Sommige entiteit-id's veranderen.** Waar er een duidelijke opvolger is, verhuist je historie
automatisch mee — je hoeft daar niets voor te doen.

| 2026.6.0 | 2026.9.0 | Historie |
|---|---|---|
| `climate.…` | `climate.thermostaat_0` | verhuist mee |
| `sensor.…_steering_power` | op het thermostaatapparaat | verhuist mee |
| `binary_sensor.…_output_0` t/m `_output_7` | `binary_sensor.hvac_module_r1` t/m `…_out3` | verhuist mee |
| `binary_sensor.…_backup_heater` | op het app-apparaat `rensonheatpumplogic` | verhuist mee |
| `binary_sensor.…_silent_mode_recurring` | idem | verhuist mee |
| `sensor.…_silent_mode_*`, `_energy_source`, `_hp_state`, `_commissioning_state` | idem | verhuist mee |
| `switch.…_silent_mode` | `binary_sensor` op het app-apparaat | **gaat verloren** |
| `sensor.…_bypass_valve` | vervalt | **gaat verloren** |

**De schakelaar voor stille modus wordt een statusweergave.** Je kunt stille modus nog wél aflezen,
maar niet meer omzetten vanuit Home Assistant. Zet je hem nu in een automatisering, dan stopt die met
werken.

*Waarom:* die instelling zit in de app `rensonheatpumplogic`, waar een wijziging alleen kan door het
hele configuratieblok terug te schrijven. Dat kan botsen met de app zelf, en een verkeerde
regelparameter kost comfort of levensduur van de warmtepomp. Hij wordt pas weer schakelbaar als er
een schrijfpad per veld is aangetoond. Instellen kan intussen gewoon in OpenMotics of de Renson
One-app. Hetzelfde geldt voor de backup heater, die in 2026.6.0 al alleen af te lezen was.

**De bypass-sensor vervalt zonder vervanger.** Die las een percentage af van uitgang 6. Dat was het
verkeerde kanaal — de bypass zit op uitgang 7 — én de waarde bleek een constante: alle acht uitgangen
melden onveranderlijk dezelfde dimmerstand. Er valt dus niets naartoe te migreren. Wat je ervoor
terugkrijgt is `Bypass-stand`, die `Open` of `Closed` meldt.

**Uitgang 6 heet nu anders.** Die stond als "Bypass-klep" in je overzicht; het is in werkelijkheid de
dummy-zoneklep van het thermostaatsysteem. Het kanaal is hetzelfde gebleven, dus je historie klopt
nog — alleen het etiket was fout.

**Je thermostaat verhuist naar een eigen apparaat.** Dashboardkaarten die naar het *apparaat*
verwijzen in plaats van naar de entiteit, moet je opnieuw koppelen.

**Er komen apparaten bij** die je nog niet kende: de drie apps op de Brain en de warmtepomp zelf. Dat
is geen ruis maar de plek waar hun versienummers en storingsmeldingen thuishoren.

### Kanttekening bij de nieuwe metingen

De temperaturen en drukken van de HVAC module en alle warmtepompwaarden worden **niet door de gateway
aangeboden**. Ze bestaan alleen in het logboek dat de app `rensonheatpumplogic` bijhoudt, als
naamloze rijtjes getallen. De integratie leest ze daar, en is eerlijk over wat dat kost:

- **Ze kunnen leeg blijven na een herstart.** De app schrijft een waarde alleen weg als die
  *verandert*. Blijft een temperatuur een uur gelijk, dan staat er een uur lang niets over in het
  log. Dat is geen storing en sneller pollen helpt er niet tegen.
- **Ze verdwijnen als de app een update krijgt.** De betekenis van elke positie hangt aan een
  specifieke app-versie, en die indeling is aantoonbaar veranderd tussen twee versies in tien weken.
  Bij een onbekende versie melden deze entiteiten niets in plaats van een verkeerd getal.
- **Van sommige staat de betekenis nog niet vast.** Elke entiteit draagt een attribuut
  `function_confidence`. Staat daar `assumed`, dan berust de toewijzing op een goed onderbouwde
  afleiding die nog niet aan de installatie is getoetst.

Daarnaast wordt élke positie van élk logrijtje ook onder een neutrale naam gepubliceerd
(`HP_UNIT/hp1 waarde 17`), als diagnostische sensor. Daarmee is straks uit te zoeken wat de
overgebleven posities betekenen.

### Opslag van je gatewaywachtwoord

Belangrijk om te weten, en het geldt voor elke Home Assistant-integratie met een wachtwoord:

**Je gatewaywachtwoord wordt in platte tekst opgeslagen, niet gehasht of versleuteld.** Dat kan ook
niet anders: de OpenMotics-gateway geeft alleen een tijdelijk token van één uur in ruil voor je
echte wachtwoord, dus de integratie moet dat wachtwoord kunnen blijven overleggen. Home Assistant
bewaart integratie-instellingen als gewone JSON in `.storage/core.config_entries`; er is geen
versleutelde opslag.

Concreet: **je wachtwoord staat leesbaar in je Home Assistant-backups.**

Wat de integratie wel doet: het tijdelijke token wordt nooit weggeschreven, wachtwoorden komen nooit
in het logboek (ook niet op debug-niveau — het wachtwoord zit in de URL, dus naïef loggen zou het
integraal lekken), en de diagnosegegevens die je kunt downloaden zijn geredigeerd.

Wat jij kunt doen:

- Maak op de gateway een **aparte gebruiker voor Home Assistant** in plaats van je hoofd- of
  installateursaccount.
- Bewaar Home Assistant-backups versleuteld, en liefst niet op een gedeelde netwerkschijf.

### Nog één ding om te weten

**Verwijder je de integratie en voeg je hem opnieuw toe, dan begint je historie opnieuw.** De
identiteit van alle apparaten en entiteiten hangt aan de configuratie-invoer, omdat de gateway geen
serienummer of ander vast hardware-kenmerk levert. Elk alternatief faalt op een moment dat je niet
aan ziet komen — bij een DHCP-wijziging, of als een module vervangen wordt. Deze faalt alleen wanneer
je het zelf doet.

### Wat níet verandert

- **Je hebt geen Renson One-account nodig.** De integratie praat uitsluitend lokaal met de Brain
  module in je eigen netwerk. Er gaat geen enkel verzoek naar de Renson-cloud — ook niet voor de
  buitentemperatuur, die uit het lokale logboek komt.
- **Alles blijft werken zonder internet.** Verwarmingsschema en presettemperaturen die je eerder via
  Renson One hebt ingesteld, staan lokaal op de Brain en blijven gewoon werken. Alleen het
  *wijzigen* van die twee vereist de Renson One-app — dat was in 2026.6.0 al zo.
- **Je presets houden hun waarden.** In het menu staat nu overal Nederlands — Klokprogramma, Afwezig,
  Handmatig — maar de onderliggende waarden `schedule`, `away` en `manual` zijn ongewijzigd. Bestaande
  automatiseringen blijven werken.

---

## 2026.6.0 — 25 juni 2026

Eerste werkende versie. Eén apparaat met thermostaatbediening (temperatuur, preset, verwarmen/koelen),
stille modus, en de status van de kleppen en pompen. Blijft beschikbaar als bevroren referentie in
`../home-assistant-renson-arean-v1`.
