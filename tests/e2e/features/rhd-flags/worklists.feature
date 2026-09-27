Feature: A worklist for every RHD flag
  The RHD Patient Flag Refresh task keeps one patient list per flag, named after the flag, with the
  patients who carry it. It replaces the ACT 2.0 Critical Data Flags screen.

  Background:
    Given the demo patients are seeded
    And I am signed in to O3 as "admin"
    And I open Patient lists, then the "System lists" tab

  Scenario: Every flag has a list, with its count
    Then I see these lists with these numbers of patients:
      | list                              | patients |
      | RHD 30-day follow-up due          | 3        |
      | RHD INR target missing            | 2        |
      | RHD bacterial sepsis not recorded | 2        |
      | RHD death not recorded on patient | 1        |
      | RHD delivery outcome overdue      | 1        |
      | RHD lost to follow-up             | 1        |
      | RHD perfusion issues not recorded | 1        |
      | RHD prophylaxis not prescribed    | 2        |
      | RHD prophylaxis overdue           | 4        |
      | RHD site infection not recorded   | 1        |

  Scenario: A list names the patients who need that action
    When I open the list "RHD bacterial sepsis not recorded"
    Then I see "Sarah Nansubuga" and "Isaac Tumusiime"
    And each row shows the patient's RHD ID and the date they joined the list

  Scenario: A patient opens from the list
    When I open the list "RHD prophylaxis overdue"
    And I click "Grace Achieng"
    Then the patient summary of "Grace Achieng" opens, showing "BPG injection overdue"

  Scenario: The lists exist on a new install before there are patients
    Given the stack was started on an empty database more than five minutes ago
    And no patients have been registered
    Then all ten RHD lists are shown under "System lists", each with 0 patients
