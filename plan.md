1. Modify `app/clients/meraki_client.py`:
   - In `get_all_relevant_meraki_clients`, filter the `devices` list *before* fanning them out to the `ThreadPoolExecutor`.
   - Use `config.get("meraki_network_ids", [])` to retrieve the network IDs.
   - If `network_ids` is not empty, filter the devices using `[device for device in devices if device.get('networkId') in network_ids]`.
   - Also filter out devices that are not switches (`MS`) or appliances (`MX`) before passing them to the executor.
   - *This step has already been completed during the exploration phase.*

2. Modify `.jules/bolt.md`:
   - Append an entry detailing this learning about preventing N+1 API calls and unnecessary external HTTP requests by filtering data collections upfront before fanning them out to a thread pool.
   - *This step has already been completed during the exploration phase.*

3. Complete pre commit steps
   - Complete pre-commit steps to ensure proper testing, verification, review, and reflection are done.

4. Submit the PR
   - Create a PR with the title: `⚡ Bolt: Filter Meraki devices by network ID before fetching`
   - Include the `💡 What`, `🎯 Why`, `📊 Impact`, and `🔬 Measurement` sections.
