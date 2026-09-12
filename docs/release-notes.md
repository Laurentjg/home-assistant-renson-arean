# Release notes

Wat elke versie voor jou als gebruiker betekent.

---

## 2026.9.0 — in voorbereiding

Deze versie herindeelt de integratie zodat ze de werkelijke Renson-opbouw volgt. Je kunt functioneel
hetzelfde, maar je ziet het anders terug en **alle entiteit-id's veranderen**. Bijwerken vraagt om de
integratie te verwijderen en opnieuw toe te voegen. Lees dit voordat je begint.

### Wat er beter wordt

- **Je installatie is nu herkenbaar.** In plaats van één apparaat "Renson Arean" zie je de Brain
  module, de HVAC module, je thermostaat, de drie apps die op de Brain draaien, en de warmtepomp zelf
  — met per app het versienummer dat ook in OpenMotics staat.
- **De drie "onbekende uitgangen" zijn opgelost.** Het bleken `Zone 1-afsluiter` (R1),
  `Bypass-klep` (OUT3) en één kanaal waar `hvac_config` niets aan toewijst (OUT1). De namen komen
  niet meer uit de code maar uit de installatie zelf: de app levert de bedradingskaart die je
  installateur bij de inbedrijfstelling heeft ingevuld.
- **Nieuwe metingen.** Systeemwatertemperatuur, systeemdruk, aanvoer- en retourtemperatuur van de
  warmtepomp, compressorfrequentie, buitentemperatuur en netspanning. Lees wel de kanttekening
  verderop — deze waarden komen langs een omweg binnen.
- **Je ziet het als je warmtepomp wegvalt.** `Warmtepomp bereikbaar` volgt nu de warmtepomp zelf: valt
  die uit terwijl de Brain gewoon doordraait, dan slaat de entiteit binnen drie minuten om, verschijnt
  er één melding in het logboek en bij herstel één melding met de duur van de storing. In eerdere
  opzetten bleef zo'n uitval volledig onzichtbaar.
- **Je thermostaatkaart laat zien of er warmte gevraagd wordt.** De kaart toont nu "verwarmen" of
  "inactief", in plaats van dat je dat uit twee losse diagnostische waarden moest afleiden.
- **Wijzigingen zijn direct zichtbaar.** Verander je de temperatuur, dan reageert de kaart meteen in
  plaats van pas bij de volgende pollronde. En hij springt niet meer terug naar de oude waarde: een
  pollronde die net vóór de cyclus van de app valt kan je wijziging niet meer ongedaan maken.
- **Rustiger logboek.** Bij het opstarten meldt de integratie van elke gegevensbron of die werkt,
  daarna alleen nog wanneer er iets verandert. Een storing wordt één keer gemeld, niet elke
  pollronde opnieuw.
- **Elk pollinterval past nu bij zijn bron.** De thermostaat elke 10 seconden, de kleppen en pompen
  elke 30, de app-instellingen elke 5 minuten, de moduleslijst elk kwartier.

### Wat je moet aanpassen

**Je moet de integratie verwijderen en opnieuw toevoegen.** Er is geen automatische overgang van
2026.6.0 naar 2026.9.0. Alle entiteit-id's zijn nieuw, en de historie van de oude entiteiten blijft
in de database staan maar wordt niet meer gevuld.

*Waarom niet gemigreerd:* een eerdere opzet zette de oude entiteiten om naar de nieuwe indeling. Dat
werkte, maar Home Assistant hernoemt een bestaand entiteit-id niet als de onderliggende identiteit
verhuist. Het resultaat was één installatie met vier naamconventies door elkaar — waaronder id's die
het verkeerde apparaat noemden, zoals een uitgang van de HVAC module die `gateway_uitgang_7` heette.
Eén schone indeling is op termijn goedkoper dan een correcte migratie naar een rommelige.

**Zo zijn de nieuwe namen opgebouwd.** Het entiteit-id noemt het *kanaal of het datapunt* en
verandert daarna nooit meer; de weergavenaam noemt de *functie* en mag per release beter worden. Een
eigen naam die je zelf instelt wint altijd.

| Wat | Entiteit-id | Weergavenaam |
|---|---|---|
| Uitgang R3 van de HVAC module | `binary_sensor.hvac_module_r3` | Driewegklep |
| Uitgang OUT3 | `binary_sensor.hvac_module_out3` | Bypass-klep |
| Je thermostaat | `climate.thermostat_0` | Thermostaat 0 |
| Stille modus | `binary_sensor.app_rensonheatpumplogic_silent_mode` | Stille modus actief |
| Aanvoertemperatuur warmtepomp | `sensor.heatpump_flow_temperature` | Aanvoertemperatuur |

Blijkt later dat R3 iets anders schakelt dan een driewegklep, dan verandert alleen het etiket. Je
automatiseringen blijven werken, want die verwijzen naar het kanaal.

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
melden onveranderlijk dezelfde dimmerstand. Wat je ervoor terugkrijgt is `Bypass-stand`, die `Open`
of `Closed` meldt.

**`Modbus-verbinding gezond` vervalt.** Die entiteit meldde in de praktijk permanent een
storing, ook terwijl de warmtepomp gewoon draaide: ze las een foutmelding uit een app die de
Modbus-koppeling helemaal niet verzorgt, en die melding verandert nooit. Gebruik in automatiseringen
voortaan `Warmtepomp bereikbaar`.

**Hysterese en stuurvermogen staan nu bij de Brain module.** Het zijn waarden van de regelaar in de
Brain, niet van je wandthermostaat — die heeft er geen register voor. Of er warmte gevraagd wordt, zie
je nog steeds op je thermostaatkaart. `Bedrijfstoestand thermostaat` heet nu `Thermostaat
ingeschakeld`: het is een aan/uit-vlag, geen werkende toestand, en de oude naam suggereerde het
tegendeel.

**`Zonetemperatuur` heet nu `Systeemwatertemperatuur`.** Metingen aan een draaiende installatie
lieten zien dat deze voeler naar bijna 40 °C loopt terwijl de kamer op 20 °C staat: het is de
watertemperatuur in het verwarmingssysteem, geen ruimtetemperatuur.

**De voelers van de boilertank en de recirculatie bestaan als entiteit, maar staan standaard uit** als
je installatie geen tapwater of recirculatie gebruikt. Heb je die subsystemen wél ingeschakeld, dan
staan ze vanzelf aan. Zet je ze handmatig aan zonder dat het subsysteem draait, dan blijven ze leeg —
een attribuut vertelt waarom.

**Uitgang 6 heet nu anders.** Die stond als "Bypass-klep" in je overzicht; het is in werkelijkheid de
dummy-zoneklep van het thermostaatsysteem. Het etiket was fout, niet het kanaal.

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

### Langetermijnstatistieken

Home Assistant bewaart van sommige waarden een statistiek voor altijd, ook na het opschonen van de
gewone historie. Deze versie kiest daar bewust weinig waarden voor — alleen de grootheden waarmee je
over een jaar nog kunt zien of je systeem net zo presteert als nu:

- buitentemperatuur
- aanvoer- en retourtemperatuur van de warmtepomp
- compressorfrequentie
- systeemdruk

De rest — instellingen, spanningen, diagnostische waarden — krijgt geen langetermijnstatistiek. Dat
houdt je database klein en je grafieken leesbaar.

Er komt **geen rendement (COP) en geen elektrisch verbruik** uit deze integratie. De warmtepomp meldt
alleen spanning en stroom, en daaruit is geen betrouwbaar verbruik af te leiden. Een aparte
energiemeter doet dat nauwkeuriger.

**Meldingen na de upgrade.** Home Assistant kan na het bijwerken melden dat het voor een aantal oude
entiteiten — bijvoorbeeld *Looptijd stille modus*, *Max. duur stille modus* of *Stuurvermogen* — geen
statistieken meer kan bijhouden, en vragen of je de bestaande statistieken wilt verwijderen. Dat mag:
deze waarden krijgen bewust geen langetermijnstatistiek meer.

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

**Verwijder je de integratie en voeg je hem opnieuw toe, dan begint je historie opnieuw** — de
langetermijnstatistieken inbegrepen. Dat geldt voor het bijwerken naar deze versie, en ook daarna. De identiteit van alle apparaten en entiteiten
hangt aan de configuratie-invoer, omdat de gateway geen serienummer of ander vast hardware-kenmerk
levert. Elk alternatief faalt op een moment dat je niet aan ziet komen — bij een DHCP-wijziging, of
als een module vervangen wordt. Deze faalt alleen wanneer je het zelf doet.

Wat wél blijft: zolang je de integratie laat staan, veranderen je entiteit-id's niet meer. Ze hangen
aan het kanaal of het datapunt, niet aan het apparaat waarop ze worden weergegeven — dus als een
meetwaarde later bij een ander apparaat blijkt te horen, verhuist de entiteit mee zonder dat je
automatiseringen breken.

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
