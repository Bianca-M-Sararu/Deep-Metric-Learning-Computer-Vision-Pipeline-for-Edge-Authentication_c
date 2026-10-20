# Deep-Metric-Learning-Computer-Vision-Pipeline-for-Edge-Authentication_c

Intelligent MFA Control System in a Secure Environment using Edge AI and IoT

An end-to-end, deterministic Multi-Factor Authentication (MFA) system designed for high-security physical access control. The architecture combines real-time Edge AI processing (YOLOv8 facial recognition without discrete GPUs) with secondary RFID verification, strictly governed by a 5-state Finite State Machine (FSM) and synchronized via asynchronous IoT cloud services.

------------------------------------------------------------------------------------------------------------------------------------

# Overall Architecture

Block diagram showing the integration between Raspberry Pi 4B, NoIR Camera, RFID Reader, Relay, Flask Backend, and Firebase Cloud.

![architecture_diagram](https://github.com/Bianca-M-Sararu/Deep-Metric-Learning-Computer-Vision-Pipeline-for-Edge-Authentication_c/blob/3d3690bee1eba625e76f2528826bba2914d0bf72/docs/architecture_diagram.png)

# FSM State Transition

Detailed flowchart depicting the 5-state Finite State Machine (Idle -> Face Recognition -> RFID Wait -> Access Decision -> Reset).

![fsm_diagram](https://github.com/Bianca-M-Sararu/Deep-Metric-Learning-Computer-Vision-Pipeline-for-Edge-Authentication_c/blob/3d3690bee1eba625e76f2528826bba2914d0bf72/docs/fsm_diagram.png)

# Live Monitoring Dashboard

Screenshot of the Flask web interface illustrating real-time access logging and live feed processing.

![Login page](https://github.com/Bianca-M-Sararu/Deep-Metric-Learning-Computer-Vision-Pipeline-for-Edge-Authentication_c/blob/3d3690bee1eba625e76f2528826bba2914d0bf72/docs/login.png)

![User_profile](https://github.com/Bianca-M-Sararu/Deep-Metric-Learning-Computer-Vision-Pipeline-for-Edge-Authentication_c/blob/3d3690bee1eba625e76f2528826bba2914d0bf72/docs/user_profile.png)

![Real_Time_Detection](https://github.com/Bianca-M-Sararu/Deep-Metric-Learning-Computer-Vision-Pipeline-for-Edge-Authentication_c/blob/3d3690bee1eba625e76f2528826bba2914d0bf72/docs/real_time.png)

------------------------------------------------------------------------------------------------------------------------------------
# Key Features

Edge AI Biometric Inference: Runs local facial recognition on a resource-constrained Raspberry Pi 4B using frame-skipping and spatial downscaling, eliminating cloud inference latency and privacy risks.

Deterministic 5-State FSM: Hardware access logic is governed by a strict Finite State Machine to guarantee fail-secure operations regardless of network connectivity.

Zero False Acceptance Rate (0% FAR): Multi-factor validation ensures zero unauthorized entries during physical benchmark testing.

Asynchronous IoT Synchronization: Access events and telemetry logs are updated in real-time to Firebase Firestore without blocking time-critical local inference threads.

Web-Based Audit Dashboard: Responsive Flask interface for monitoring access logs, managing authorized user profiles, and viewing live streams.

# Finite State Machine (FSM) Logic

**State 0** (IDLE): System monitors camera feed at low frame rate.

**State 1** (FACE_DETECT): Face detected; local YOLOv8 pipeline extracts features and validates against authorized database embeddings.

**State 2** (RFID_WAIT): Primary biometric factor passed; system opens a timed window awaiting secondary RFID card scan.

**State 3** (VALIDATE_ALL): Dual-factor correlation check (Biometrics + RFID ID).

**State 4** (ACCESS_GRANT / DENY): Physical relay triggers for unlocked access OR immediate fail-secure lockdown occurs. Log event dispatched to Firebase.


------------------------------------------------------------------------------------------------------------------------------------

# Performance Benchmarks

Physical testing on the hardware prototype yielded the following metrics:

![Metrics](https://github.com/Bianca-M-Sararu/Deep-Metric-Learning-Computer-Vision-Pipeline-for-Edge-Authentication_c/blob/5f15d957074a7e8f3d7936ec64d1817854e1a2f3/docs/metrics.png)

------------------------------------------------------------------------------------------------------------------------------------
# Installation & Setup

Prerequisites:

- Hardware: Raspberry Pi 4B (4GB/8GB recommended), Raspberry Pi NoIR Camera Module, RC522 RFID Module, 5V Relay Lock Module.

- OS: Raspberry Pi OS (64-bit) with Python 3.10+

1. Clone the Repository
   git clone https://github.com/Bianca-M-Sararu/Deep-Metric-Learning-Computer-Vision-Pipeline-for-Edge-Authentication_c.git
2. Environment Setup
Create a virtual environment and install dependencies:
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt

3.Security Credentials Configuration

⚠️ Security Notice: Credentials and private keys are excluded from version control.
Obtain your service account credentials from the Firebase Console.
Save the key as firebase-auth.json in the root folder.
Define your environment variables in an .env configuration file.

# 🚀 Running the System

Start the Edge Control Loop (Raspberry Pi)
  python env_mfa.py

Start the Local Web Dashboard
  python app.py
