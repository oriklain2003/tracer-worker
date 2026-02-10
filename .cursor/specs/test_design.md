# New logic tests

## Context

Until now we collected data and analyzed it with the anomaly pipeline, we adjusted the code and the parameters to make it good, good means that its no longer creates false alarms, now we want to make it better then good we want to go through each rule and each flight and see what can be made better.

See monitor.py, rules folder 


## Mission 

To be able to change the pipeline and do adjustments on specific rules with out making a mess in other rules and logics we need to have a way to see what anomalies changed their status and what normal flights become anomalies, and only then we can judge the changes.

For that i want to build tests, 2 types one that is looking at random flights and anomalies and reanalyze them and the second type is for going trough all the flights and anomalies and again reanalyze them.

I need it to be fast overall and extra fast thats why we do option 1, the report should have before and after for each changed flight with these parameters: is_anomaly matched rules, if i missed something we should add it.

### Tables 

See db.md in /docs

We do not need to use live and feedback schema, only research for anomalies and normal flights.


### To Do

1. create new file script named algorithm_verification.py
2. connect it to the db using our known connection way
3. think on a fast way to analyze a lot of docs
4. create a way to call the analyze function in monitor.py (its important we use that file, because that is where the service mostly work )
5. create 2 types of verification one random flights fast and one for all a little slower.
6. create a nice way to see the verification run report, we need a way to just see what flights was changed and what has changed in short words.

# IMPORTANT

Write clean and readable code!!!!
Do not write code just to make it work, really think on it and make sure its good