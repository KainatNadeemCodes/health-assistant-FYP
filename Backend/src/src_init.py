"""
src/__init__.py
================
AI-Powered Smart Health Assistant  |  Version 1.1  |  Group: F25PROJECT664B0

This file marks the `src/` directory as a proper Python package.

It allows all internal modules to be imported cleanly across the project, for example:

    from src import preprocessing, classifier, feature_extraction
    from src.triage import generate_triage
    import src.database as db

Keeping everything inside a structured package makes the
project modular, organized, and easier to maintain.
It also ensures consistent imports during development and deployment.


Module Overview
---------------
preprocessing
    Handles text cleaning and medical input validation
    (FR16 / TC-05).

feature_extraction
    Loads the trained TF-IDF vectorizer and converts
    cleaned symptom text into numerical features.

classifier
    Loads the trained model and provides top-K predictions.

triage
    Generates risk-level advice and detects red-flag symptoms
    (FR4 / FR6 / FR7 / FR17).

explainability
    Identifies which symptoms influenced the prediction and
    generates explanation text for the user (FR13).

database
    Manages the SQLite layer for users, consultations, and feedback.

voice_processor
    Handles microphone input and speech-to-text conversion (UC-02).

pdf_generator
    Generates structured consultation reports in PDF format (TC-12).
"""