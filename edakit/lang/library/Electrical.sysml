library package Electrical {
    doc /* edakit's electrical domain: pins, components, nets, blocks, the circuit, its metadata, requirements and
         * derivation rules – what an edakit project is in SysML v2's terms. Generated into no project; imported
         * by every export of `edakit graph sysml`. */
    private import ScalarValues::*;
    private import ISQ::*;
    private import SI::*;

    attribute def Range { attribute min : ScalarQuantityValue; attribute max : ScalarQuantityValue; }
    attribute def VoltageRange :> Range {
        doc /* a net's v: min and max over all intended operating states */
        attribute :>> min : ElectricPotentialDifferenceValue;
        attribute :>> max : ElectricPotentialDifferenceValue;
    }
    enum def Purpose { 'private'; gift; sale; }
    enum def Binding { must; should; may; }
    enum def Status { draft; accepted; dropped; }

    port def Pin {
        doc /* a pin of a component: the symbol's number, the entry's name and role */
        attribute number : String;
        attribute name : String[0..1];
        attribute role : String[0..1];
    }
    abstract part def Component {
        doc /* a component of the graph; the attributes are the graph's keys */
        attribute designator : String;
        attribute lcsc : String[0..1];
        attribute mpn : String[0..1];
        attribute value : String[0..1];
        attribute board : String[0..1];
        attribute bom : Boolean default true;
        attribute label : String[0..1];
        attribute notes : String[0..1];
        port pins : Pin[*];
    }
    part def Resistor :> Component { attribute resistance : ResistanceValue[0..1]; }
    part def Capacitor :> Component { attribute capacitance : CapacitanceValue[0..1]; }
    part def Inductor :> Component { attribute inductance : InductanceValue[0..1]; }
    part def Diode :> Component;
    part def LED :> Diode {
        attribute color : String[0..1];
        attribute vfTyp : ElectricPotentialDifferenceValue[0..1];
        attribute vfMin : ElectricPotentialDifferenceValue[0..1];
        attribute vfMax : ElectricPotentialDifferenceValue[0..1];
        attribute vfAt : ElectricCurrentValue[0..1];
        attribute rs : ResistanceValue[0..1];
        attribute ifMax : ElectricCurrentValue[0..1];
    }
    part def Microcontroller :> Component;   part def Module :> Component;      part def IC :> Component;
    part def Transistor :> Component;        part def Connector :> Component;   part def Regulator :> Component;
    part def Button :> Component;            part def Switch :> Component;      part def Potentiometer :> Component;
    part def Audio :> Component;             part def Testpoint :> Component;   part def BatteryHolder :> Component;
    part def Fuse :> Component;
    part def Other :> Component { attribute 'type' : String; }   // a graph type the library lacks

    connection def Net {
        doc /* a net: n-ary, every end a Pin; the attributes are the net's keys */
        attribute name : String;
        attribute v : VoltageRange[0..1];
        attribute fn : String[0..1];
        attribute fnBus : String[0..1];
        attribute bus : String[0..1];
        attribute pwmHz : FrequencyValue[0..1];
        attribute clockHz : FrequencyValue[0..1];
        attribute notes : String[0..1];
    }
    connection def Cable {
        doc /* wires between two connectors, pin to pin; the cable is no part */
        attribute name : String;
        attribute rOhmPerWire : ResistanceValue[0..1];
        attribute lengthM : LengthValue[0..1];
    }
    abstract part def Block :> Component {
        doc /* a definition of the language: ports, parameters, parts, nets, derivations */
    }
    part def Circuit {
        doc /* a project's graph */
        attribute name : String;
        attribute version : String[0..1];
        attribute date : String[0..1];
        attribute description : String[0..1];
        attribute purpose : Purpose[0..1];
        attribute market : String[0..1];
        attribute purposeNotes : String[0..1];
        attribute ground : String default "GND";
        part components : Component[*];
        connection nets : Net[*];
        connection cables : Cable[*];
    }

    metadata def Accept { attribute code : String; attribute reason : String; }
    metadata def Lock { doc /* the firmware relies on this pin being on this net */ attribute net : String; }
    metadata def Decision { attribute id : String[1..*]; }
    metadata def Layout { attribute fixed : String[*]; attribute edge : String[*]; attribute notes : String[*]; }
    metadata def Derivation {
        doc /* a record of section 7: the rule, its inputs as text, the derived value, the window */
        attribute rule : String;
        attribute inputs : String;
        attribute 'derived' : Real;
        attribute unit : String;
        attribute window : Real[2];
    }

    requirement def CircuitRequirement {
        doc /* R-: one testable sentence as doc, with edakit's binding and status; verify names the evidence */
        attribute 'binding' : Binding;
        attribute status : Status;
        attribute 'verify' : String[*];
    }
    requirement def Need {
        doc /* N-: what someone wants, in their words */
        attribute who : String[0..1];
        attribute status : Status;
    }
    verification def Evidence {
        doc /* rows of the gate protocol, a sign-off, a script, an acceptance step */
        attribute what : String;
    }

    calc def SeriesResistor {
        doc /* R = (vOn − vf(i)) / i with vf(i) = vfTyp + rs·(i − vfAt): edakit's rule series_resistor */
        in i : ElectricCurrentValue;  in vOn : ElectricPotentialDifferenceValue;
        in vfTyp : ElectricPotentialDifferenceValue;  in vfAt : ElectricCurrentValue;  in rs : ResistanceValue;
        return r : ResistanceValue;
    }
    calc def Divider { in vIn : ElectricPotentialDifferenceValue; in vOut : ElectricPotentialDifferenceValue;
                       in i : ElectricCurrentValue; return rTop : ResistanceValue; return rBottom : ResistanceValue; }
    calc def Pullup { in v : ElectricPotentialDifferenceValue; in iSink : ElectricCurrentValue;
                      in vOl : ElectricPotentialDifferenceValue; return r : ResistanceValue; }
    calc def RC { in fC : FrequencyValue; in c : CapacitanceValue[0..1]; in r : ResistanceValue[0..1];
                  return rOut : ResistanceValue[0..1]; return cOut : CapacitanceValue[0..1]; }
}
