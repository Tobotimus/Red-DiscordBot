CREATE OR REPLACE FUNCTION
  jsonb_set_deep(target jsonb, identifiers text[], new_value jsonb) RETURNS jsonb AS
$$
  DECLARE
    cur_value_type text;
    idx integer := 1;
    num_identifiers CONSTANT integer := array_length(identifiers, 1);
  BEGIN
    LOOP
      IF idx = num_identifiers THEN
        RETURN jsonb_set(target, identifiers, new_value);
      ELSE
        cur_value_type := jsonb_typeof(target #> identifiers[:idx]);
        IF cur_value_type IS NULL THEN
          -- Parent key didn't exist in JSON before - insert new object
          target := jsonb_set(target, identifiers[:idx], '{}'::jsonb);
        ELSEIF cur_value_type != 'object' THEN
          -- We can't set the sub-field of a null, int, float, array etc.
          RAISE EXCEPTION 'Cannot set sub-field of (%)', cur_value_type;
        END IF;
      END IF;
      idx := idx + 1;
    END LOOP;
  END;
$$ LANGUAGE plpgsql;


DROP AGGREGATE IF EXISTS json_agg_all(VARIADIC primary_keys any[], json_data jsonb);
CREATE AGGREGATE json_agg_all(VARIADIC primary_keys any[], json_data jsonb) (

);
