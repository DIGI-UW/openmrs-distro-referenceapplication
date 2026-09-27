Feature: A flag clears when the data is recorded
  patientflags re-checks a patient's flags whenever clinical data for that patient is saved, so a
  flag clears as soon as the missing data is recorded. The chart shows it after a reload.

  Background:
    Given the demo patients are seeded
    And I am signed in to O3 as "admin"

  Scenario: Recording the hospitalization outcomes clears three flags
    When I open the patient summary of "Sarah Nansubuga"
    And I click the flag "Perfusion Issues missing on Procedures and Outcomes"
    And I click "Open form" on the row "Perfusion Issues"
    And I answer "No" to "Perfusion Issues", "Site Infection" and "Bacterial Sepsis"
    And I save the form
    And I reload the patient summary
    Then "Sarah Nansubuga" has no RHD flag

  Scenario: Recording an injection clears the overdue flag
    When I open the patient summary of "Grace Achieng"
    And I click the flag "BPG injection overdue"
    And I open the form "RHD BPG Delivery"
    And I enter today's date as "Date of Injection"
    And I save the form
    And I reload the patient summary
    Then "Grace Achieng" has no RHD flag

  Scenario: A patient whose flag cleared leaves its list at the next refresh
    Given "Grace Achieng" has no RHD flag
    When the RHD Patient Flag Refresh task runs
    And I open the list "RHD prophylaxis overdue"
    Then "Grace Achieng" is not on the list
