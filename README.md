# Simple SSVEP framework

A simple python 3.7 based SSVEP framework to easily conduct open and closed loop SSVEP experiments.

## Design
For a visual overview of the design, see ```framework_design.png```.
All communication is done using labstreaminglayer (LSL). 

## Installation
``` pip install -r requirements.txt```

## Usage
- Change config.yml to the right parameters, speficially the correct streamInlet name of the amplifier. Also don't forget to change the closedLoop parameter.

- in seperate terminals:
``` python decoder.py```
```bash python UI_..._.py````

- press escape to abort experiment (will close after each trial in the open loop experiment)

## options
For a open loop labeled experiment, you can change the labels.txt file to the labels to show in order, corresponding with the directions in config.yml. You can change them manually or generate a sequence with generate_labels.py


## Contributing
Please contact me

## License
[MIT] (https://choosealicense.com/licenses/mit/)
