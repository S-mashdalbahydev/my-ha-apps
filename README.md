# Pie Assistant Apps Repository

This repository contains the core local applications for the **Pie Assistant** project, built as a privacy-first cognitive voice assistant designed to run completely offline on **Home Assistant OS** using a Raspberry Pi 5. 

For a complete and in-depth breakdown of user requirements, system architecture, and algorithmic design, please refer to the official project report document **M16_GP1 (3) (1).pdf**. The foundational architecture layout and project signatures can also be cross-referenced with **image_97a2a0.jpg**.

---

## 🚀 Core Applications

This suite focuses strictly on the local ecosystem pipeline, contained within the following three target applications:

### 1. `pie-assistantV3`
The central orchestration and reasoning engine of the smart assistant. 
* **Custom NLU Routing:** Employs a multi-tiered ranking algorithm to score and match natural language commands against local device names, areas, and custom aliases.
* **RAG Pipeline Control:** Coordinates the localized Retrieval-Augmented Generation (RAG) framework, fetching search results and converting text segments into structured chunks.
* **Intent Handling:** Intelligently routes straightforward home commands directly to local device services while forwarding contextual knowledge queries to the local AI engine.

### 2. `Ollama`
The on-device artificial intelligence inference server.
* **Local Language Models:** Runs highly optimized, quantized small language models (such as `smollm2:360m`) entirely on edge hardware.
* **Vector Embeddings:** Powers local semantic vector generation (via models like `nomic-embed-text`) to perform rapid vector similarity lookups in RAM.
* **Absolute Data Isolation:** Eliminates cloud-based dependencies, ensuring that conversational text data is never sent to external servers.

### 3. `cognitive_home`
The predictive intelligence layer that introduces context-aware routine tracking.
* **Habit Learning:** Automatically processes historical state transitions and events recorded in the local Home Assistant SQLite database to extract repeating daily routines.
* **Explainable Confidence:** Ranks recurring behaviors using a clear statistical probability engine based on successful occurrences against missed events. The evaluation is computed as: Confidence = occurrences / (occurrences + missed).
* **Proactive Automation:** Evaluates immediate timeline windows to push proactive system suggestions to the UI, allowing users to accept or decline routine automation cards.


## 🛠️ Installation & Setup via Add-on Store

The applications in this repository run as isolated Docker containers within Home Assistant OS and must be installed through the built-in Add-on Store.

1. **Host Setup:** Verify that your system is powered by an active deployment of **Home Assistant OS** on a Raspberry Pi 5.
2. **Add Custom Repository:** * Open your Home Assistant dashboard and navigate to **Settings** > **Add-ons** > **Add-on Store**.
   * Click the three vertical dots (menu) in the top-right corner and select **Repositories**.
   * Paste the URL for this GitHub repository into the text field and click **Add**.
3. **Install the Add-ons:** * Close the repositories dialog and refresh the Add-on Store page.
   * Scroll down to find the newly added **Pie Assistant Apps** category.
   * Click on and **Install** the `pie-assistantV3`, `Ollama`, and `cognitive_home` add-ons.
   
