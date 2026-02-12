Here is the translation of the document into English.

# **New Rules for Tracer \- February 26**

Rule Name: Non-Commercial Off-Route Circular Flight

**Trigger:** Identification of an aircraft not classified as a commercial passenger/cargo plane, performing a takeoff and return to land at the same airport (or in its immediate vicinity), without a flight plan to another destination.

**Logic / Threshold Conditions:**

* **Classification:** The ICAO Type or Category of the aircraft is not "Commercial" (e.g., training aircraft, light aircraft, or military aircraft).

* **Route Deviation:** The aircraft is outside the "tube" (Buffer) of recognized aviation routes (ATS Routes) for over 60% of its flight time.

* **Circle Closure:** The geographic distance between the takeoff point and the landing point (or start of the approach process) is less than 5 nautical miles.

* **Duration:** Accumulated flight time exceeding 15 minutes (to exclude technical malfunctions causing an immediate return to land after takeoff).

**Deviation / Detection:**

* The system will mark an anomaly when a pattern of "area flight" or "observation" is detected – meaning, accumulation of significant flight time outside standard routes, accompanied by maneuvers that are not route-based (like the zigzags and loops seen in the track of CHLE1C), and ending with a return to the point of origin.

---

Rule Name: Distance Trend Diversion \- DTD

1\. The Triggers

* **Real-Time Trigger:** Identification of a consistent trend of geographic distancing from the original destination airport for a defined period.

* **Backup Trigger (Retrospective):** Identification of flight termination (speed \< 30 knots) at a location that is not the destination airport and not the origin airport.

2\. Logic & Thresholds To distinguish between an aircraft performing a Holding pattern and an aircraft abandoning the route, we will define the "Continuous Distancing Index":

* **Development Logic:**

  * The system needs to activate the "Continuous Distancing Index" based on the following conditions:

* **Distance Trend Analysis:**

  * **Check Window:** 5 minutes (300 seconds).

  * **Sampling:** Sampling the distance from the original destination airport every 10 seconds.

  * **Anomaly Condition:** The distance from the destination must increase consistently (positive trend) in at least 80% of the samples over 5 consecutive minutes.

  * **Rationale:** In a holding pattern (circuit), the distance increases and decreases alternately. In a diversion to another destination, the distance will increase linearly. Five minutes is a time significantly longer than a standard circuit (approx. 2 minutes).

* **Validation Filters:**

  * **Cruise Filter:** The rule will only trigger for aircraft that have passed an altitude of FL180 during their flight (to exclude low altitude training flights).

  * **Current Altitude Filter:** The aircraft is below its last cruise altitude (indicates descent towards a new destination).

* **Post-Landing Backup:**

  * If the real-time detection was missed, the system will perform a check at the moment of stopping (speed 0):

  * **Condition:** The final distance from the original destination airport is greater than 20 nautical miles (NM) and as long as the landing airport is not the origin airport (meaning, RTB was not performed).

3\. Deviation / Detection The system will classify the event according to two levels:

* **Intent Identification (Real-Time):**

  * The moment the aircraft completed 5 minutes of continuous distancing from the destination \+ it is outside the planned route (Corridor).

  * **Status:** "Anomaly: Route abandonment and distancing trend from destination".

* **Landing Verification (Event Closure):**

  * The aircraft stopped (speed 0\) at a foreign field.

  * **Status:** "Anomaly: Landing at unplanned destination".

---

Rule Name: Performance Mismatch

**Definition** Identification of a logical and physical contradiction between the declared identity of the aircraft (ICAO Code/Callsign) and its actual performance, using the database as a physical "truth ruler".

**Trigger:** Reception of ADS-B data containing the parameters: icao24 (Hex address), callsign, Ground Speed (GS), Vertical Rate (VR), Altitude, and Heading.

**Logic & Thresholds** The system will pull the weight category (FAA\_Weight) from the ACD\_Data.csv file and calculate the maximum turn rate threshold (T) according to three altitude layers:

* 1\. Approach and Holding Layer (Below 10,000 feet):

  * **Threshold (T):** Uniform for all aircraft types \- **4.0 degrees per second**.

  * **Rationale:** Allowing space to perform Holding Patterns and relatively sharp approach turns at low speed.

* 2\. Transition Layer (Between 10,000 and 25,000 feet) \- The Linear Model:

  * In this range, the threshold (T) is calculated as a function of altitude. It starts at 4.0 (at 10k altitude) and decreases gradually to the cruise threshold (at 25k altitude).

  * **Formula for developers:** $T \= 4.0 \- (Current Altitude \- 10,000) \\times Gradient$.

  * The Gradient is determined by the aircraft weight (from the ACD file):

    * **Heavy:** Gradient is 0.000166 (drop from 4.0 to 1.5).

    * **Large:** Gradient is 0.000133 (drop from 4.0 to 2.0).

    * **Small:** Gradient is 0.000033 (drop from 4.0 to 3.5).

* 3\. Cruise Layer (Above 25,000 feet):

  * The threshold (T) is fixed according to aircraft weight:

    * **Heavy / Super:** 1.5 degrees per second.

    * **Large:** 2.0 degrees per second.

    * **Small / Small+:** 3.5 degrees per second.

**Deviation / Detection**

* The system will classify the anomaly as "**Performance Mismatch**".

* **Insight for Operator:**

  * "The aircraft (\[ICAO\_Code\]), defined as \[FAA\_Weight\], is performing a turn of \[X\] degrees per second at altitude \[Altitude\]. The calculated threshold for the transition layer at this altitude is \[T\]. The maneuver exceeds the physical norm by \[Z\]%; Suspicion of military aircraft under civilian cover."

---

Rule Name: Performance & Identity Mismatch \- PIM

**Definition** Identification of a logical and physical contradiction between the declared identity of the aircraft (ICAO Code/Callsign) and its performance in the field, using the database as a physical "truth ruler".

**Trigger:** Reception of an ADS-B data sequence containing the following parameters: icao24 (Hex address), callsign, Ground Speed, and Vertical Rate.

**Logic & Thresholds** The rule is based on cross-referencing real-time ADS-B data against the ACD\_Data.csv file. Developers must perform a Join by the ICAO\_Code field and pull the FAA\_Weight and Physical\_Class\_Engine fields.

1\. Automatic Performance Category Mapping: The system will classify the aircraft into a threshold category according to data from the file:

* **Light:** If FAA\_Weight contains "Small" or "Small+".

* **Commercial/Medium:** If FAA\_Weight is "Large" and Physical\_Class\_Engine is "Jet" or "Turboprop".

* **Heavy:** If FAA\_Weight is "Heavy" or "Super".

* **Rotorcraft:** If Physical\_Class\_Engine is "Turboshaft".

2\. Thresholds Table: The anomaly will trigger if the aircraft exceeds the following thresholds for **30 consecutive seconds**:

| Category (per ACD) | Speed Limit (GS) | Climb Limit (Vertical Rate) |
| :---- | :---- | :---- |
| Light | \> 220 knots | \> 2,500 fpm |
| Commercial / Medium | \> 350 knots (below 10k ft) | \> 5,500 fpm |
| Heavy | \> 350 knots (below 10k ft) | \> 5,500 fpm |
| Rotorcraft | \> 200 knots | \> 3,500 fpm |
|   |  |  |

3\. Built-in Impersonation Detection (Emitter Category 6):

* If the aircraft transmits a civilian Callsign but its Emitter Category (EC) in transmission is **6** (High Performance), this is an immediate anomaly regardless of performance.

* If the ICAO\_Code is associated in the ACD database with a distinct military manufacturer (e.g., Fairchild A-10) but the Callsign is civilian – trigger an alert.

**Deviation / Detection**

* The system will pop up an anomaly of type "**Identity Spoofing**".

* **Insight for Operator:** "The aircraft is transmitting an identity of \[ICAO\_Code\] but exceeds the physical performance envelope defined for this model in the Database by \[X\]%. The registered weight category is \[FAA\_Weight\]. High suspicion of military aircraft/UAV under civilian cover."

**Technical Notes:**

* **Noise Cancellation:** Speed spikes resulting from momentary GPS changes (Jitter) will be filtered using a 30-second continuity check.

* **Retrieval Key:** The ICAO\_Code is the only key for retrieving data from the ACD.

* Do not rely on the pilot's declaration in the transponder regarding the aircraft type.

---

Rule Name: Identity-Origin Conflict \- IOC

**Definition:** Identification of a logical contradiction between the aircraft's country of registration (derived from the Hex code) and the operator's country (derived from the Callsign prefix).

**Trigger:** Reception of an ADS-B message containing the fields icao24 (Hex address) and callsign simultaneously.

**Logic & Thresholds:** The rule is based on cross-referencing the "Nation State" of two separate identity fields:

* **Registration Country Identification (Hex Origin):** The system will perform a Look-up for the Hex code against the ICAO block allocation table to determine which country the aircraft officially belongs to.

* **Operator Country Identification (Callsign Operator):** The system will extract the first 3 characters of the Callsign (the Prefix) and identify the airline and the country associated with it.

* **Anomaly Condition:** If the country identified in the Hex is different from the country identified in the Callsign.

* **Exclusions:**

  * **Wet Lease List:** The system will cross-reference against a list (updated manually or via API) of known lease agreements (e.g., a Portuguese aircraft operated regularly for a German company).

* **Wet Lease Verification Mechanism (Addition to Rule):**

  * Before popping an anomaly, the system will perform a 'historical consistency' check:

  * **14-Day Check:** Has this Hex been observed with this Callsign prefix in more than 5 different flights in the last 14 days?

    * **IF YES:** Classify as 'Established Lease' and move to Low Priority status (Green).

    * **IF NO:** Pop alert as 'New Identity Mismatch' (Red/Orange).

  * **"Offshore" Registrations:** Exclusion of private aircraft registered in countries like Bermuda (BPR), Cayman Islands (CYM), or Isle of Man (IMN), which serve as global registration hubs.

**Resources for Developers:** The development team must implement the following databases in the system Database:

* **Hex Code Mapping to Countries (ICAO 24-bit Address Space):** Something found on GitHub \- Link.

* **Airline Prefix Mapping (ICAO Airline Designators):**

  * Search codes by company and country: AvCodes Search Tool.

  * Consolidated list (ICAO Doc 8585): Wikipedia \- List of Airline Codes.

**Deviation / Detection:**

* The system will pop up an anomaly of type "**Identity-Origin Conflict (IOC)**".

* **Insight for Operator:** "The aircraft is transmitting a callsign of company \[Company Name\] from \[Country A\], but its Hex address is registered in \[Country B\]. Suspicion of use of a foreign transponder or manual identity spoofing."

* **Example:** An aircraft with an Egyptian Hex (06A...) transmitting a Callsign of a Lebanese company (MEA).

---

Rule Name: Ghost Aircraft Detection \- GAD

**Definition:** Identification of an aircraft transmitting a Hex code (ICAO 24-bit address) associated in global databases with an aircraft whose activity status is "Scrapped", "Stored", "Written off", or "De-registered".

**Trigger:** Reception of the first ADS-B message containing the field icao24 (Hex address).

**Logic & Thresholds:** The rule is based on cross-referencing against "blacklists" of inactive statuses:

* **Status Check:** Upon receiving the Hex, the system will check the local Database (updated from global repositories) regarding the current status of the aircraft.

* **Anomaly Condition:** If the returned status is one of the following:

  * Scrapped / Broken up (The aircraft was dismantled into parts).

  * Stored (The aircraft is in long-term storage, e.g., in an "aircraft graveyard").

  * De-registered (Registration cancelled due to sale or decommissioning).

  * Unknown/Invalid (Hex code never assigned to any aircraft).

* **"Update Gap" Exclusion:** To prevent false alarms on aircraft recently sold or returned from storage, the system will check the date of the last status update.

  * If the status is "Stored" for less than 30 days, the anomaly will be marked in yellow (Low Priority).

**Resources for Developers:**  This is a rule that relies 100% on data quality in the Database. The development team must implement the following sources:

* **OpenSky Network Aircraft Database:** The most comprehensive open-source database. Includes fields for built, firstflightdate, and status. Link: OpenSky Aircraft Database.

* **ADS-B Exchange Database:** Huge database including information on military and private aircraft not always appearing on commercial sites. Link (GitHub): ADSBX-Aircraft-Database.

* **Planespotters.net API (or Web Scraping):** The "Gold Standard" for aircraft status. Updates when an aircraft moved to Storage and when it was dismantled.

**Deviation / Detection:**

* The system will pop up an anomaly of type "**Ghost Identity Detected**".

* **Insight for Operator:** "The aircraft is transmitting a Hex code officially identified as 'Scrapped' or 'Stored' since year \[YYYY\]. High suspicion of using a stolen identity for a covert mission."

---

Rule Name: Endurance vs. Type Breach \- ETB

**Definition:** Identification of an aircraft staying airborne for a prolonged time significantly exceeding the physical maximum capability (Max Endurance) of the aircraft model declared in the ADS-B data.

**Trigger:** Identification of a "**Takeoff Event**" defined as a combination of the following conditions:

* Change of onground status from true to false.

* Increase in Ground Speed (GS) above **80 knots** (for jet/propeller aircraft).

**Logic & Thresholds:** The system manages an active time counter measuring net flight duration:

* **Setting Zero Point ($T\_0$):** The system records the exact Timestamp of the takeoff event (Takeoff\_Time).

* **Air Time Calculation:** At any given moment, flight time is calculated as: $Current\\\_Time \- Takeoff\\\_Time$.

* **Performance Cross-Reference:** The system pulls the Max Endurance figure from the Database according to the aircraft's ICAO Type Code.

* **Anomaly Condition:** The alert will trigger if the current flight duration is **120%** higher than the maximum capability of the model.

| ICAO Type | Category Description | Max Flight Time (Hours) | Alert Threshold (120%) |
| :---- | :---- | :---- | :---- |
| C172 | Cessna 172 (Light Aircraft) | 5 hours | 6 hours |
| B738 | Boeing 737-800 | 7 hours | 8.4 hours |
| UAV | "UAV (Impersonation)" | 24+ hours | Immediate alert upon breach |
|   |  |  |  |

---

Rule Name: In-Flight Signal Discontinuity \- ISD

**Definition** Identification of an event where an aircraft stops or starts transmitting ADS-B data while airborne, provided there is proof (current or recent historical) of proper coverage in the area.

**Trigger**

* **Signal Loss:** Cessation of data reception from a Hex code that was in status onground: false for more than 3 minutes.

* **Signal Pop-up:** First reception of a Hex code in the system when it is already in status onground: false.

**Logic & Thresholds** For the event to be classified as an anomaly and not a standard "coverage hole", developers must verify that all the following conditions are met:

1. **Physical Constraints:**

   * **Altitude:** The aircraft is at an altitude exceeding **3,000 feet** (AGL).

   * **Speed:** The aircraft is flying at a speed exceeding **120 knots**.

   * **Geographic Distance:** The event occurs at a distance greater than **15 nautical miles** (NM) from any known airport (to exclude landings/takeoffs below the receiver's horizon).

2. **Historical Neighbor Correlation:**

   * Instead of checking only in real-time, the system will check the "receiver vitality" in the area:

   * **Logic:** The system will scan a radius of **50 nautical miles** (50 NM) from the disconnection/connection point.

   * **Anomaly Condition:** If at least one other aircraft was identified transmitting data in that radius in the **last 30 minutes**.

   * **Rationale:** If another aircraft passed there 10 minutes ago and was received well, the regional receiver is functional. The disappearance of the current aircraft at this point is not due to lack of coverage, but due to a proactive action.

3. **Velocity Consistency:**

   * The aircraft maintained stable speed and altitude (deviation of less than 5%) in the 3 minutes preceding the disappearance.

   * **Rationale:** Sudden disconnection in a stable state indicates a manual shutdown ("Binary Drop") and not a gradual descent behind a mountain or ground obstacle.

**Deviation / Detection**

* The system will pop up an anomaly of type "**Tactical Signal Dropout**".

* **Insight for Operator:** "The aircraft (\[ICAO\_Code\]) disappeared at altitude \[Altitude\] and speed \[Speed\]. Coverage verification performed: 3 aircraft found transmitting within a 50-mile radius in the last 20 minutes. The area is not defined as a Blind Spot; high suspicion of intentional signal disconnection to hide route."

**Technical Notes:**

* **Memory Buffer:** The system needs to keep a "memory" of 30 minutes of all spatial traffic (including aircraft that have already left the sector) for Correlation cross-referencing.

* **Geo-Fencing:** Polygons defined as "permanent no-coverage areas" (like the middle of the ocean) must be automatically excluded to prevent alert flooding.

---

Rule Name: Commercial Footprint Absence \- CFA

The core idea of the rule is based on the difference between transmitted identity and commercial authorization: While a pilot can enter any "Name" (Callsign) they want into the transponder, they cannot invent a "client file" in global logistics and ticketing systems. The rule exposes "shadow flights" by checking if the aircraft's destination exists in the "real world" of civil aviation through two internal mechanisms:

1. **The Address Rule (IATA Code):**

   * Every civil airport that sells tickets or moves cargo holds a 3-letter "IATA Code" (like TLV or JFK) used for commercial purposes. Military bases, however, usually hold only a 4-letter operational code (ICAO), and do not have a civilian code because they are simply not part of the global tourism or trade map.

2. **The Proof of Life Rule (Schedule):**

   * Civil airlines must publish their flights in advance in the global schedule to perform orderly registration of cargo and passengers.

   * If a heavy aircraft lands at a point where the civil flight schedule is "zero" (like in Nevatim), the system understands that this flight has no legal civilian "cover" and that its identity is a cover for classified logistical/military activity.

**The Combination:** Even if a military base has a civilian code (like certain logistical bases), it will always fail the second rule, because no civil airline publishes regular flights to a military base.

**Trigger:** Identification of takeoff or landing of an aircraft meeting the following two conditions:

* **Classification:** Weight category **Heavy** or **Large** (heavy cargo/transport aircraft).

* **Identity:** Callsign of a known commercial company (e.g., LOY, ELY, CAL).

**Logic / Thresholds (The Double-Lock):** The system runs a double check against global databases to determine if the destination is "legitimately civilian":

* **The IATA Test (Bureaucratic Identity):** Does the airport have an IATA code (3 letters)?.

* **The Schedule Test (Operational Activity):** Is there **even one flight** (passenger or cargo) registered in the global flight schedule (Schedule) for this airport in the next 48 hours?.

**Anomaly Hierarchy:**

* **Critical Severity (Red):** Destination airport has **no IATA code** and also **no flight schedule** (indicates a closed military base).

* **High Severity (Orange):** Destination airport **has IATA code** (like Nevatim \- VTM), but its **flight schedule is empty** (indicates a logistical/military base used for "shadow" flights).

**Deviation / Detection:**

* The system will pop up an anomaly of type "**Unauthorized Commercial Route**".

* **Insight for Operator (Based on case LOY688):** "Heavy cargo aircraft (B744) uses identity of LOT (LOY), but operates in an airport with no regular commercial activity (LLNV). No registered flight of this company found in the global flight schedule on the reported route. High suspicion of military supply flight under civilian cover."

---

Rule Name: Quota & Fleet Diversity Anomaly \- QFDA

*(Burns' Rule (Request) \- High Complexity Level)*

**Definition:** Identification of an anomalous flight performed beyond the approved daily flight quota in the official schedule, or use of an aircraft (Hex) not associated with the regular fleet operating the route.

**Trigger:** Reception of an aircraft on a known commercial route (e.g., Tehran-Beirut) carrying a Callsign of a regular operator.

**Logic / Thresholds (The Rhythmic Logic):** The system performs a real-time cross-reference between traffic in the field and the schedule and history of the line:

* **Quota Check:**

  * The system counts how many flights of the same operator (e.g., Mahan Air) have already been performed on this route in the last 24 hours.

  * **Anomaly Condition:** The number of actual flights is higher than the number of planned flights in the official schedule for that day.

* **"Foreign Guest" Check (Fleet Match):**

  * The system checks if the specific Hex code performed this route at least once in the last 90 days.

  * **Anomaly Condition:** The aircraft is identified as "new to route" (First time on route), while other flights on the line are performed by a fixed and known group of aircraft.

* **Flight Line Check:**

  * The system checks and weighs the usage volume of the route and generates a daily, weekly, etc., average that counts the number of flights performed on that line each day (e.g., Tehran-Damascus line is performed 2 times a day or 2 times a week).

  * **Anomaly Condition:** If the line is performed 3 times on the same day (exceeds the regular daily line quota and/or meets the previous criteria) it requires consideration.

**Deviation / Detection:**

* The system will pop up an anomaly of type "**Extra-Schedule Fleet Intrusion**".

* **Insight for Operator:** "A fourth flight was identified on a line where only 3 flights are planned. The mission is performed by an aircraft (Hex: \[X\]) never observed on this route. High suspicion of special supply flight (weapons) exploiting an unplanned time window under civilian company identity."

* **Added Value:** This rule "catches" the smuggler precisely because of their precision – they try to behave normally, but the system knows they have no "place" in the company's tight schedule.

**The Distilled Concept:**

* The rule does not look for a "lie" in the aircraft data, but an **anomaly in statistics**.

* In civil aviation, every flight is money and a strict schedule. A flight not registered in the "books" or an aircraft that "popped in for a visit" on a line unfamiliar to it, are the most distinct signs of covert operational activity.  
