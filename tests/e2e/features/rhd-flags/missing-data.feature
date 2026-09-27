Feature: What is missing behind a flag
  Clicking an orange flag opens the RHD workspace, "Missing data". It lists, for each of the
  patient's flags that has a gap query, the form, the date it was saved, the missing field and the
  days pending, with a button that opens the form. It replaces the ACT 2.0 row and its link.

  Background:
    Given the demo patients are seeded
    And I am signed in to O3 as "admin"

  Scenario: The workspace lists every gap behind the patient's flags
    When I open the patient summary of "Sarah Nansubuga"
    And I click the flag "Perfusion Issues missing on Procedures and Outcomes"
    Then the workspace "Missing data" opens
    And it has a table for each of these flags, in which the form is "Procedures and Outcomes":
      | flag                              | missing           |
      | RHD perfusion issues not recorded | Perfusion Issues  |
      | RHD site infection not recorded   | Site Infection    |
      | RHD bacterial sepsis not recorded | Bacterial Sepsis  |
    And each row shows the date of the Procedures and Outcomes encounter and the days since it

  Scenario: Open form opens the saved encounter
    When I open the patient summary of "Isaac Tumusiime"
    And I click the flag "Bacterial Sepsis missing on Procedures and Outcomes"
    And I click "Open form" on the row "Bacterial Sepsis"
    Then the form "Procedures and Outcomes" opens with the answers already recorded on that encounter
    And its question "Bacterial Sepsis" has no answer

  Scenario: A gap with no saved form to complete
    When I open the patient summary of "Agnes Apio"
    And I click the flag "Secondary Antibiotic Prophylaxis missing on RHD Consultation Visit"
    Then the workspace says "No saved form is waiting to be completed. Record the missing data on a new form."
    And "Open clinical forms" opens the Clinical forms list

  Scenario: Flags without a gap query are left out
    When I open the patient summary of "Winnie Auma"
    And I click the flag "INR Target missing on RHD INR Monitoring"
    Then the workspace has tables for "RHD INR target missing" and "RHD 30-day follow-up due"
    And it has no table for "RHD prophylaxis overdue"

  Scenario: A red flag opens clinical forms instead
    When I open the patient summary of "Moses Ochieng"
    And I click the flag "BPG injection overdue"
    Then the Clinical forms list opens
