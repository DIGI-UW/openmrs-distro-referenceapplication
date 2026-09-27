Feature: RHD flags on the patient chart
  Each ACT 2.0 critical data rule and registry signal is a patient flag, shown at the top of the
  patient summary. Clinical risks are red, missing data is orange.

  Background:
    Given the demo patients are seeded
    And I am signed in to O3 as "admin"

  Scenario Outline: A seeded patient carries the flags their record calls for
    When I open the patient summary of "<patient>"
    Then I see exactly these flags: <flags>

    Examples: Missing data (orange)
      | patient           | flags                                                                                   |
      | Samuel Okello     | "Secondary Antibiotic Prophylaxis missing on RHD Consultation Visit"                   |
      | Ruth Nakato       | "Date of Patient Follow-Up due on Procedures and Outcomes"                             |
      | Peter Kato        | "INR Target missing on RHD INR Monitoring"                                             |
      | Isaac Tumusiime   | "Bacterial Sepsis missing on Procedures and Outcomes"                                  |
      | Harriet Adong     | "Delivery mode missing on RHD Pregnancy"                                               |
      | Robert Ouma       | "Death recorded on a form but not on the patient"                                      |
      | Sarah Nansubuga   | "Bacterial Sepsis missing on Procedures and Outcomes", "Perfusion Issues missing on Procedures and Outcomes", "Site Infection missing on Procedures and Outcomes" |

    Examples: Clinical risk (red)
      | patient           | flags                                                                                   |
      | Grace Achieng     | "BPG injection overdue"                                                                 |
      | Joseph Opio       | "BPG injection overdue", "Lost to follow-up: no data for 7 months"                     |

  Scenario Outline: A patient whose care is up to date carries no RHD flag
    When I open the patient summary of "<patient>"
    Then I see no RHD flag

    Examples:
      | patient           |
      | Esther Nambi      |
      | Patience Akello   |
      | Daniel Ssempijja  |
      | Emmanuel Wanyama  |

  Scenario: Risk and missing data are told apart
    When I open the patient summary of "Winnie Auma"
    Then "BPG injection overdue" is red, with the risk flag marker
    And the patient banner shows "1 risk flag"
    And "INR Target missing on RHD INR Monitoring" is orange
    And "Date of Patient Follow-Up due on Procedures and Outcomes" is orange

  Scenario: A flag cannot be hidden from the chart
    When I open the patient summary of "Grace Achieng"
    Then there is no button to edit or hide the patient's flags
