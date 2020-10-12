# Simple SSVEP framework

A simple python 3.7 based SSVEP framework for open and closed loop SSVEP experiments.

## Design
For a visual overview of the design, see ```framework_design.jpg```.
All communication is done using labstreaminglayer (LSL). 

## Installation
``` pip install -r requirements.txt```

## Usage
- Change config.yml to the right parameters, specifically the correct streamInlet name of the amplifier. Also don't forget to change the closedLoop parameter.

- In seperate terminals:
```python decoder.py```
```python UI_..._.py```

- Press escape to abort experiment (will close after each trial in the open loop experiment)

## Options
For an open loop labeled experiment, you can change ```labels.txt```. Labels are shown in order, corresponding with the directions in ```config.yml```. You can change them manually or generate a sequence with ```generate_labels.py```

## Further notes
Framework should run without significant framedrops. (Assuming you have at least an i5 processor or comparable), since the UI and Decoder run on seperate cores. However, LabRecorder uses as much processing power as needed, so when recording large amounts of data, framedrops are likely to happen.

The supplied classifier is currently not implemented (completely) modular and has not be thouroughly tested  on performance. So if you intent to change the algorithm, it might require some extra work.

## Contributing
Please contact me

## License
[MIT] (https://choosealicense.com/licenses/mit/)
