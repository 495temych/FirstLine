/** A row of buttons that pick one option, with a legend. */
export function Pills<T extends string>(
  props: Readonly<{
    legend: string;
    options: readonly T[];
    value: T;
    label: (option: T) => string;
    onChange: (value: T) => void;
  }>,
) {
  return (
    <fieldset className="pills">
      <legend>{props.legend}</legend>
      {props.options.map((option) => (
        <button
          key={option}
          type="button"
          aria-pressed={props.value === option}
          onClick={() => {
            props.onChange(option);
          }}
        >
          {props.label(option)}
        </button>
      ))}
    </fieldset>
  );
}
