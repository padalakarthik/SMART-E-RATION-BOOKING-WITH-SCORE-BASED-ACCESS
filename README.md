# SMART-E-RATION-BOOKING-WITH-SCORE-BASED-ACCESS

The Smart e-Ration Booking with Score-Based Access project is an innovative full-stack web application developed to modernize India’s Public Distribution System (PDS) by introducing automation, transparency, and data-driven decision-making in ration distribution. The system aims to overcome the inefficiencies of the existing manual process—such as long queues, corruption, and lack of prioritization—by using a digital, score-based model that allocates booking slots based on household vulnerability.
A score-based prioritization mechanism (ranging from 0 to 100) is implemented to dynamically evaluate each beneficiary’s eligibility. This scoring system is determined using parameters such as family size, income level, Below Poverty Line (BPL) status, and historical usage patterns. Beneficiaries with higher vulnerability scores receive priority during booking, ensuring fair access to essential commodities for the most deserving families.



Problem Statement:

The Public Distribution System (PDS) in India remains a cornerstone of food security, supporting over 800 million beneficiaries through a vast network of Fair Price Shops (FPS). Despite its scale, the system is plagued by deep-rooted inefficiencies stemming from outdated manual processes. Citizens endure long queues, often waiting for hours under harsh conditions, only to face stockouts or delayed service due to poor inventory planning. There is no mechanism for advance booking, leading to chaotic crowds and unequal access—particularly affecting vulnerable groups such as the elderly, pregnant women, and low-income families. Record-keeping is predominantly paper-based, prone to errors, loss, and manipulation, which erodes trust and enables leakage of subsidized commodities. Administrators operate without real-time data, making demand forecasting impossible and resulting in either overstocking (wastage) or understocking (shortages). Distributors lack visibility into center-wise booking patterns, hindering efficient resource allocation. Most critically, there is no system to monitor user engagement or incentivize regular participation, allowing inactive or ineligible cardholders to retain access while genuine beneficiaries struggle. These systemic gaps not only reduce operational efficiency but also compromise the core PDS objective: ensuring timely, transparent, and equitable delivery of essential commodities to those who need them most.

PROPOSED METHODOLOGY:

To overcome these challenges, we propose the Smart e-Ration Booking with Score-Based Access system—a fully automated, web-based platform designed for scalability, transparency, and fairness in low-resource environments. The system is developed using Flask, a lightweight Python web framework, to manage routing, session-based authentication, and business logic, while Tailwind CSS (via CDN) ensures a modern, mobile-responsive, and consistent user interface across all devices. Users access the platform through any web browser to register, log in, view their profile, and book ration slots at least five days in advance, with a strict limit of one booking per month per card to prevent hoarding. A dynamic engagement score (0–100) serves as the gatekeeper: only users with a score of 35 or higher can book, with an initial score of 50 assigned to all registered users. This score is automatically updated on the last day of every month using APScheduler, a robust background job scheduler that triggers a daily job at 00:05 AM but executes the update only when the current date matches the month’s final day—ensuring zero manual intervention and 100% reliability. The scoring logic is simple yet powerful: users with at least one booking in the current month gain +5 points (capped at 100), while those with no activity lose –10 points (floored at 0), creating a self-regulating mechanism that rewards consistency and penalizes dormancy.

Demand forecasting is integrated using Linear Regression from scikit-learn, trained on historical booking data aggregated by date. The model uses dayofyear as a feature to predict total bookings for the next seven days, achieving a Mean Absolute Error (MAE) of approximately 2.5, enabling administrators to anticipate demand spikes and coordinate with suppliers proactively. Results are visualized in real time using Chart.js within the admin dashboard.

The platform features role-based dashboards:
•
Users view their score, booking history, and available slots with real-time availability indicators (low/medium/high).
•
Admins access full user management, manual score overrides, demand forecasts, and system-wide analytics.
•
Distributors filter bookings by center, date, or card number to monitor operational load.
