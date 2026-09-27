Feature: A new patient is flagged and joins the worklist
  A patient with an RHD or acute rheumatic fever diagnosis and no secondary antibiotic prophylaxis
  recorded is flagged "RHD prophylaxis not prescribed" (ACT 2.0 rule 1). The flag is raised when
  the data is saved; the patient joins the flag's list at the next refresh.

  Background:
    Given I am signed in to O3 as "admin"

  Scenario: Diagnosis without prophylaxis raises the flag
    When I register a new female patient "Rose Aciro", born 14 February 2012
    Then she is given an RHD ID
    When I start an "RHD Clinic Visit" for her
    And I record "RHD Patient Information" with "Category at Diagnosis" set to "RHD B"
    And I reload her patient summary
    Then she carries the flag "Secondary Antibiotic Prophylaxis missing on RHD Consultation Visit"

  Scenario: She joins the list at the refresh
    Given "Rose Aciro" carries the flag "Secondary Antibiotic Prophylaxis missing on RHD Consultation Visit"
    When the RHD Patient Flag Refresh task runs
    And I open the list "RHD prophylaxis not prescribed"
    Then "Rose Aciro" is on the list, joined today

  Scenario: Prescribing prophylaxis clears the flag, and she leaves the list
    Given "Rose Aciro" is on the list "RHD prophylaxis not prescribed"
    When I click her flag "Secondary Antibiotic Prophylaxis missing on RHD Consultation Visit"
    Then the workspace says "No saved form is waiting to be completed. Record the missing data on a new form."
    When I click "Open clinical forms" and open "RHD Consultation Visit"
    And I enter today's date as "Date of Consultation Visit"
    And I set "Secondary Antibiotic Prophylaxis" to "Q28 day BPG"
    And I save the form
    And I reload her patient summary
    Then she has no RHD flag
    When the RHD Patient Flag Refresh task runs
    And I open the list "RHD prophylaxis not prescribed"
    Then "Rose Aciro" is not on the list
