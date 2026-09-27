Feature: A flag and a list made by hand
  Flags normally come from distro/configuration/flags. A flag can also be created in the legacy
  admin UI; the refresh gives every enabled flag a list. A list made by hand is never changed by
  the RHD Flags module.

  Background:
    Given the demo patients are seeded
    And I am signed in to the legacy admin UI as "admin"

  Scenario: A flag created in the admin UI gets its own list
    When I open Administration, "Manage Flags", and add a flag:
      | Name      | RHD echocardiogram not recorded                                        |
      | Criteria  | patients with an RHD diagnosis and no RHD Echocardiogram encounter     |
      | Evaluator | SQL                                                                     |
      | Message   | No echocardiogram recorded                                              |
      | Priority  | RHD Data Quality                                                        |
      | Tag       | RHD                                                                     |
    And I save the flag
    And the RHD Patient Flag Refresh task runs
    Then O3 shows a list "RHD echocardiogram not recorded" under "System lists"
    And the flag appears, orange, on the chart of "Esther Nambi"
    And clicking it opens the Clinical forms list

  Scenario: A list made by hand is left alone
    Given I am signed in to O3 as "admin"
    When I open Patient lists, click "New list", name it "Echo outreach" and save it
    And I add "Esther Nambi" to it
    And the RHD Patient Flag Refresh task runs
    Then "Echo outreach" still lists "Esther Nambi" and nobody else

  Scenario: The module's settings
    When I open Administration, "Settings", and filter on "rhdflags"
    Then I see "rhdflags.listFlagTag", empty, so every enabled flag gets a list
    And I see "rhdflags.listCohortType", "System List"
    And I see one "rhdflags.gapQuery" setting for each Critical data flag that lists its gaps
